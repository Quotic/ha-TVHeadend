"""Live TV camera for TVHeadend (streams the selected channel)."""
import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import go2rtc
from .const import (
    CONF_AUDIO_VIA_GO2RTC, CONF_GO2RTC_RTSP_PORT, CONF_GO2RTC_URL,
    CONF_STREAM_PROFILE, DEFAULT_AUDIO_VIA_GO2RTC, DEFAULT_GO2RTC_RTSP_PORT,
    DEFAULT_GO2RTC_URL, DEFAULT_STREAM_PROFILE, DOMAIN,
    SIGNAL_CHANNEL_SELECTED)
from .entity import tvh_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TVHeadend camera from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TVHCamera(hass, entry, data)])


class TVHCamera(Camera):
    """A single camera that streams whichever channel is selected."""

    _attr_name = "TVHeadend"
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, hass, entry, data):
        """Initialize the camera."""
        super().__init__()
        self.hass = hass
        self._entry = entry
        self._data = data
        self._tvh = data['tvh']
        self._logo_cache = {}

        self._attr_unique_id = '{}_camera'.format(entry.entry_id)
        self._attr_device_info = tvh_device_info(entry.entry_id, self._tvh)

    @property
    def _selected(self):
        """Return the currently selected channel dict (may be empty)."""
        return self._data.get('selected') or {}

    async def async_added_to_hass(self):
        """Subscribe to channel-change notifications from the select entity."""
        self.async_on_remove(async_dispatcher_connect(
            self.hass,
            SIGNAL_CHANNEL_SELECTED.format(self._entry.entry_id),
            self._handle_channel_change))

    @callback
    def _handle_channel_change(self):
        """Restart the stream when the selected channel changes."""
        # Stream.stop() is synchronous (the Camera base calls it the same way);
        # dropping the cached stream forces a new one with the new source.
        if self.stream is not None:
            self.stream.stop()
            self.stream = None
        self.async_write_ha_state()

    async def stream_source(self):
        """Return the stream source for the selected channel.

        When audio-via-go2rtc is enabled, define a go2rtc stream that copies the
        video and transcodes the audio of the (clean) 'pass' feed, and return
        its RTSP URL so Home Assistant plays it with sound. Falls back to the
        direct TVHeadend URL (video only) if go2rtc cannot be reached.
        """
        uuid = self._selected.get('uuid')
        if not uuid:
            return None

        options = self._entry.options
        if options.get(CONF_AUDIO_VIA_GO2RTC, DEFAULT_AUDIO_VIA_GO2RTC):
            api_url = options.get(CONF_GO2RTC_URL, DEFAULT_GO2RTC_URL)
            name = go2rtc.stream_name(self._entry.entry_id)
            src = 'ffmpeg:{}#video=copy#audio=aac#audio=opus'.format(
                self._tvh.stream_url(uuid, 'pass'))
            rtsp_port = options.get(
                CONF_GO2RTC_RTSP_PORT, DEFAULT_GO2RTC_RTSP_PORT)
            session = async_get_clientsession(self.hass)
            if await go2rtc.ensure_stream(session, api_url, name, src):
                return go2rtc.rtsp_url(api_url, name, rtsp_port)
            _LOGGER.warning(
                'go2rtc unavailable; falling back to direct stream (no audio).')

        profile = options.get(CONF_STREAM_PROFILE, DEFAULT_STREAM_PROFILE)
        return self._tvh.stream_url(uuid, profile)

    async def async_will_remove_from_hass(self):
        """Clean up the go2rtc stream when the camera is removed."""
        options = self._entry.options
        if options.get(CONF_AUDIO_VIA_GO2RTC, DEFAULT_AUDIO_VIA_GO2RTC):
            await go2rtc.delete_stream(
                async_get_clientsession(self.hass),
                options.get(CONF_GO2RTC_URL, DEFAULT_GO2RTC_URL),
                go2rtc.stream_name(self._entry.entry_id))

    async def async_camera_image(self, width=None, height=None):
        """Return the channel logo as the still image (never tunes a tuner)."""
        icon_url = self._selected.get('icon_url')
        if not icon_url:
            return None
        if icon_url not in self._logo_cache:
            self._logo_cache[icon_url] = await self._tvh.fetch_image(icon_url)
        return self._logo_cache[icon_url]

    @property
    def extra_state_attributes(self):
        """Expose the currently selected channel name."""
        return {'channel': self._selected.get('name')}
