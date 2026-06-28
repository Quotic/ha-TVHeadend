"""Channel picker for TVHeadend (drives the camera)."""
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, SIGNAL_CHANNEL_SELECTED
from .entity import tvh_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TVHeadend channel select from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TVHChannelSelect(hass, entry, data)])


class TVHChannelSelect(SelectEntity):
    """A select entity listing channels; selection drives the camera."""

    _attr_icon = 'mdi:format-list-bulleted'

    def __init__(self, hass, entry, data):
        """Initialize the channel select."""
        self.hass = hass
        self._entry = entry
        self._data = data
        self._tvh = data['tvh']
        self._channels = self._tvh.channels

        self._attr_name = "TVHeadend Channel"
        self._attr_unique_id = '{}_channel_select'.format(entry.entry_id)
        self._attr_options = [chan['name'] for chan in self._channels]
        self._attr_current_option = None
        self._attr_device_info = tvh_device_info(entry.entry_id, self._tvh)

    async def async_select_option(self, option):
        """Select a channel and notify the camera to switch."""
        channel = next(
            (chan for chan in self._channels if chan['name'] == option), None)
        if channel is None:
            _LOGGER.error('Unknown channel selected: %s', option)
            return

        self._data['selected'] = {
            'uuid': channel['uuid'],
            'name': channel['name'],
            'icon_url': channel.get('icon_public_url'),
        }
        self._attr_current_option = option
        self.async_write_ha_state()

        async_dispatcher_send(
            self.hass, SIGNAL_CHANNEL_SELECTED.format(self._entry.entry_id))
