"""Support for TVHeadEnd sensors."""
import logging

from homeassistant.const import EVENT_STATE_CHANGED, ATTR_ENTITY_ID
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.sensor import SensorEntity

from . import CONF_SENSORS, DATA_TVH, SIGNAL_UPDATE_TVH

_LOGGER = logging.getLogger(__name__)

INPUT_SELECT_DOMAIN = 'input_select'
SERVICE_SET_OPTIONS = 'set_options'
SERVICE_SELECT_OPTION = 'select_option'


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the TVHeadend sensors."""
    if discovery_info is None:
        return

    name = 'tvheadend'
    sensors = discovery_info[CONF_SENSORS]
    tvh = hass.data[DATA_TVH]

    all_sensors = []

    for index, sensor in enumerate(sensors):
        sname = '{}_{}'.format(name, index)
        all_sensors.append(TVHSensor(hass, sname, tvh.stream_list[index]))

    async_add_entities(all_sensors, True)


class TVHSensor(SensorEntity):
    """TVH sensor representation."""

    def __init__(self, hass, name, stream):
        """Initialize a TVH sensor."""
        self.hass = hass
        self._stream = stream
        self._name = name
        self._state = self._stream.channel_name
        _LOGGER.debug('Setup new stream sensor: %s', name)

        self._input_entity = 'input_select.tv_stream_{}'.format(self._name.split('_')[1])
        self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._handle_input_select_updates)

    async def _handle_input_select_updates(self, event):
        """Handle state change updates for input_select."""
        entity_id = event.data.get(ATTR_ENTITY_ID)
        if entity_id != self._input_entity:
            return

        new_state = event.data.get('new_state').state
        if new_state == "Inactive":
            return

        if new_state != self._stream.active_service:
            _LOGGER.debug('Action user-input on: %s to state %s', entity_id, new_state)
            await self._stream.change_service(new_state)

    async def async_added_to_hass(self):
        """Register update dispatcher."""

        @callback
        def async_tvh_update():
            """Update callback."""
            self.async_schedule_update_ha_state(True)

        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_TVH, async_tvh_update)

    @property
    def name(self):
        """Return the channel name of the stream."""
        index = self._name.split('_')[1]
        return 'TV Stream #{}'.format(index)

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
            _LOGGER.error('%s is not a valid input_select entity.', self._input_entity)
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
                'options': self._reorder_list(self._stream.service_name_list, option),
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
            _LOGGER.error("Desired first item isn't in list, returning original list.")
            return inlist

        return [first] + [item for item in inlist if item != first]
