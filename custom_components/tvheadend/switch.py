"""Support for TVHeadEnd switches."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN, SIGNAL_UPDATE_TVH
from .entity import tvh_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TVHeadend switches from a config entry."""
    tvh = hass.data[DOMAIN][entry.entry_id]['tvh']

    switches = [
        TVHSwitch(entry.entry_id, index, stream)
        for index, stream in enumerate(tvh.stream_list)
    ]

    async_add_entities(switches, True)


class TVHSwitch(SwitchEntity):
    """Representation of a TVH switch."""

    def __init__(self, entry_id, index, stream):
        """Initialize a TVH switch."""
        self._stream = stream
        self._index = index
        self._attr_unique_id = '{}_switch_{}'.format(entry_id, index)
        self._attr_device_info = tvh_device_info(entry_id, self._stream.server)
        _LOGGER.debug('Setup new stream switch: %s', self._attr_unique_id)

    async def async_added_to_hass(self):
        """Register update dispatcher."""
        @callback
        def async_tvh_update():
            """Update callback."""
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_TVH, async_tvh_update))

    @property
    def name(self):
        """Return the name."""
        return 'TV Stream #{}'.format(self._index)

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return None

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:autorenew'

    @property
    def available(self):
        """Return True if entity is available."""
        return self._stream.is_active

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self._stream.change_service()
