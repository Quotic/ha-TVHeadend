"""Support for TVHeadend."""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ATTR_TARGET_INDEX, ATTR_TARGET_SERVICE, CONF_MAXCONN, DEFAULT_MAXCONN,
    DOMAIN, EPG_SCAN_INTERVAL, PLATFORMS, SERVICE_SERVICE_SWITCH,
    SIGNAL_UPDATE_TVH, TVH_SCAN_INTERVAL)
from .pytvheadend.tvheadend import TVHeadend

_LOGGER = logging.getLogger(__name__)

SERVICE_TVH_SCHEMA = vol.Schema({
    vol.Required(ATTR_TARGET_INDEX): cv.string,
    vol.Required(ATTR_TARGET_SERVICE): cv.string,
})


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

    async def async_update_epg(now=None):
        """Refresh the EPG cache and notify entities."""
        await tvh.fetch_epg()
        async_dispatcher_send(hass, SIGNAL_UPDATE_TVH)

    @callback
    def force_update_tvh_data(msg):
        """Force update of all entities."""
        _LOGGER.debug('TVHeadend force update callback fired.')
        async_dispatcher_send(hass, SIGNAL_UPDATE_TVH)

    await async_update_tvh_data()
    await async_update_epg()
    tvh.add_update_callback(force_update_tvh_data)

    unsubs = [
        async_track_time_interval(
            hass, async_update_tvh_data, TVH_SCAN_INTERVAL),
        async_track_time_interval(
            hass, async_update_epg, EPG_SCAN_INTERVAL),
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

    return unload_ok
