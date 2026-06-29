"""Support for TVHeadEnd sensors."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN, SIGNAL_UPDATE_TVH
from .entity import tvh_device_info

_LOGGER = logging.getLogger(__name__)

INPUT_SELECT_DOMAIN = 'input_select'
SERVICE_SET_OPTIONS = 'set_options'
SERVICE_SELECT_OPTION = 'select_option'


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TVHeadend sensors from a config entry."""
    tvh = hass.data[DOMAIN][entry.entry_id]['tvh']

    sensors = [
        TVHSensor(hass, entry.entry_id, index, stream)
        for index, stream in enumerate(tvh.stream_list)
    ]

    async_add_entities(sensors, True)


class TVHSensor(SensorEntity):
    """TVH sensor representation."""

    def __init__(self, hass, entry_id, index, stream):
        """Initialize a TVH sensor."""
        self.hass = hass
        self._stream = stream
        self._index = index
        self._state = self._stream.channel_name
        self._attr_unique_id = '{}_sensor_{}'.format(entry_id, index)
        self._attr_device_info = tvh_device_info(entry_id, self._stream.server)
        _LOGGER.debug('Setup new stream sensor: %s', self._attr_unique_id)

        self._input_entity = 'input_select.tv_stream_{}'.format(index)

    async def _handle_input_select_updates(self, event):
        """Act on the linked input_select changing."""
        new_state = event.data.get('new_state')
        if new_state is None or new_state.state in (None, 'Inactive'):
            return

        if new_state.state != self._stream.active_service:
            _LOGGER.debug('Action user-input on: %s to state %s',
                          self._input_entity, new_state.state)
            await self._stream.change_service(new_state.state)

    async def async_added_to_hass(self):
        """Register update dispatcher and input_select tracking."""

        @callback
        def async_tvh_update():
            """Update callback."""
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_TVH, async_tvh_update))
        self.async_on_remove(async_track_state_change_event(
            self.hass, [self._input_entity],
            self._handle_input_select_updates))

    @property
    def name(self):
        """Return the channel name of the stream."""
        return 'TV Stream #{}'.format(self._index)

    @property
    def available(self):
        """Return True if entity is available."""
        return self._stream.is_active

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:television-classic'

    @property
    def should_poll(self):
        """No polling needed within TVH."""
        return False

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Update latest state."""
        self._state = self._stream.channel_name
        await self._update_input_select(self._stream.active_service)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            'active_service': self._stream.active_service,
            'service_list': self._stream.service_name_list,
        }

    async def _update_input_select(self, option=None):
        """Update associated input select."""
        if self.hass.states.get(self._input_entity) is None:
            _LOGGER.error('%s is not a valid input_select entity.',
                          self._input_entity)
            return

        curr_state = self.hass.states.get(self._input_entity).state

        if not self._stream.service_name_list:
            if curr_state == 'Inactive':
                return
            data = {'options': ['Inactive'], 'entity_id': self._input_entity}
        else:
            if curr_state == option:
                return
            data = {
                'options': self._reorder_list(
                    self._stream.service_name_list, option),
                'entity_id': self._input_entity,
            }

        _LOGGER.debug('Update input_select with: %s', data)
        await self.hass.services.async_call(
            INPUT_SELECT_DOMAIN, SERVICE_SET_OPTIONS, data)

        if option:
            data = {'option': option, 'entity_id': self._input_entity}
            if curr_state != option:
                await self.hass.services.async_call(
                    INPUT_SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)

    def _reorder_list(self, inlist, first=None):
        """Reorder given list moving specified value to index 0."""
        if first not in inlist:
            _LOGGER.error(
                "Desired first item isn't in list, returning original list.")
            return inlist

        return [first] + [item for item in inlist if item != first]
