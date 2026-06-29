"""Support for TVHeadend."""
import logging
import time

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME)
from homeassistant.core import SupportsResponse, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_CHANNEL, ATTR_HOURS, ATTR_TARGET_INDEX, ATTR_TARGET_SERVICE,
    CONF_MAXCONN, DEFAULT_EPG_HOURS, DEFAULT_MAXCONN, DOMAIN, PLATFORMS,
    SERVICE_GET_EPG, SERVICE_SERVICE_SWITCH, SIGNAL_UPDATE_TVH,
    TVH_SCAN_INTERVAL)
from .pytvheadend.tvheadend import TVHeadend

_LOGGER = logging.getLogger(__name__)

SERVICE_TVH_SCHEMA = vol.Schema({
    vol.Required(ATTR_TARGET_INDEX): cv.string,
    vol.Required(ATTR_TARGET_SERVICE): cv.string,
})

GET_EPG_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CHANNEL): cv.string,
    vol.Optional(ATTR_HOURS, default=DEFAULT_EPG_HOURS):
        vol.All(vol.Coerce(int), vol.Range(min=1, max=168)),
})


def _format_event(event):
    """Shape a raw EPG event for the service response."""
    def iso(epoch):
        return dt_util.utc_from_timestamp(epoch).isoformat() if epoch else None

    return {
        'channel': event.get('channelName'),
        'channel_number': event.get('channelNumber'),
        'title': event.get('title'),
        'subtitle': event.get('subtitle'),
        'description': event.get('description'),
        'start': iso(event.get('start')),
        'end': iso(event.get('stop')),
        'genre': event.get('genre'),
    }


async def async_setup_entry(hass, entry):
    """Set up TVHeadend from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    username = entry.data.get(CONF_USERNAME) or None
    password = entry.data.get(CONF_PASSWORD) or None
    maxconn = entry.options.get(
        CONF_MAXCONN, entry.data.get(CONF_MAXCONN, DEFAULT_MAXCONN))

    tvh = TVHeadend(host, port, usr=username, pwd=password, maxconn=maxconn)

    if not await tvh.start():
        await tvh.stop()
        return False

    async def async_update_tvh_data(now=None):
        """Refresh the active subscription list and notify entities."""
        await tvh.fetch_subscription_list()
        async_dispatcher_send(hass, SIGNAL_UPDATE_TVH)

    @callback
    def force_update_tvh_data(msg):
        """Force update of all entities."""
        _LOGGER.debug('TVHeadend force update callback fired.')
        async_dispatcher_send(hass, SIGNAL_UPDATE_TVH)

    await async_update_tvh_data()
    tvh.add_update_callback(force_update_tvh_data)

    unsubs = [
        async_track_time_interval(
            hass, async_update_tvh_data, TVH_SCAN_INTERVAL),
    ]

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        'tvh': tvh,
        'unsubs': unsubs,
        # currently selected channel for the camera, set by the select entity
        'selected': {},
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, SERVICE_SERVICE_SWITCH):
        async def async_service_handler(service):
            """Handle tvh service calls."""
            index = int(service.data[ATTR_TARGET_INDEX])
            target = service.data[ATTR_TARGET_SERVICE]
            data = next(iter(hass.data[DOMAIN].values()))
            await data['tvh'].stream_list[index].change_service(target.upper())

        hass.services.async_register(
            DOMAIN, SERVICE_SERVICE_SWITCH, async_service_handler,
            schema=SERVICE_TVH_SCHEMA)

    if not hass.services.has_service(DOMAIN, SERVICE_GET_EPG):
        async def async_get_epg(service):
            """Return EPG events for a channel/time window as response data."""
            data = next(iter(hass.data[DOMAIN].values()))
            channel = service.data.get(ATTR_CHANNEL)
            hours = service.data.get(ATTR_HOURS, DEFAULT_EPG_HOURS)
            now = time.time()
            events = await data['tvh'].get_epg(
                channel=channel, start=now, stop=now + hours * 3600)
            return {'events': [_format_event(event) for event in events]}

        hass.services.async_register(
            DOMAIN, SERVICE_GET_EPG, async_get_epg,
            schema=GET_EPG_SCHEMA, supports_response=SupportsResponse.ONLY)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass, entry):
    """Reload the entry when its options change (e.g. stream slot count)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    """Unload a TVHeadend config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        for unsub in data['unsubs']:
            unsub()
        await data['tvh'].stop()

        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_SERVICE_SWITCH)
            hass.services.async_remove(DOMAIN, SERVICE_GET_EPG)

    return unload_ok
