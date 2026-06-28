"""Support for TVHeadEnd sensors."""
import logging

from homeassistant.const import EVENT_STATE_CHANGED, ATTR_ENTITY_ID
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.sensor import SensorEntity
import homeassistant.util.dt as dt_util

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

    sensors += [
        TVHChannelSensor(entry.entry_id, tvh, channel)
        for channel in tvh.channels
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
        self.hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._handle_input_select_updates)

    async def _handle_input_select_updates(self, event):
        """Handle state change updates for input_select."""
        entity_id = event.data.get(ATTR_ENTITY_ID)
        if entity_id != self._input_entity:
            return

        new_state = event.data.get('new_state').state
        if new_state == "Inactive":
            return

        if new_state != self._stream.active_service:
            _LOGGER.debug('Action user-input on: %s to state %s',
                          entity_id, new_state)
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


class TVHChannelSensor(SensorEntity):
    """Now/Next EPG sensor for a single TVHeadend channel."""

    _attr_should_poll = False
    _attr_icon = 'mdi:television-box'

    def __init__(self, entry_id, tvh, channel):
        """Initialize a channel EPG sensor."""
        self._tvh = tvh
        self._uuid = channel['uuid']
        self._channel_name = channel.get('name')
        self._channel_number = channel.get('number')
        self._icon_url = channel.get('icon_public_url')
        self._current = None
        self._next = None

        self._attr_name = self._channel_name
        self._attr_unique_id = '{}_epg_{}'.format(entry_id, self._uuid)
        self._attr_device_info = tvh_device_info(entry_id, tvh)
        _LOGGER.debug('Setup new channel EPG sensor: %s', self._attr_unique_id)

    async def async_added_to_hass(self):
        """Register update dispatcher."""

        @callback
        def async_tvh_update():
            """Update callback."""
            self.async_schedule_update_ha_state(True)

        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_TVH, async_tvh_update)

    async def async_update(self):
        """Recompute the current and next programs from the EPG cache."""
        self._current, self._next = self._tvh.epg_now_next(self._uuid)

    @property
    def native_value(self):
        """Return the title of the program currently airing."""
        if self._current is None:
            return None
        return self._current.get('title')

    @property
    def entity_picture(self):
        """Return the channel logo URL, if available."""
        if not self._icon_url:
            return None
        return '{}/{}'.format(self._tvh.root_url, self._icon_url)

    @property
    def extra_state_attributes(self):
        """Return now/next program details."""
        attrs = {
            'channel': self._channel_name,
            'channel_number': self._channel_number,
        }
        if self._current is not None:
            attrs.update({
                'start': self._as_datetime(self._current.get('start')),
                'end': self._as_datetime(self._current.get('stop')),
                'subtitle': self._current.get('subtitle'),
                'description': self._current.get('description'),
                'genre': self._current.get('genre'),
            })
        if self._next is not None:
            attrs.update({
                'next_title': self._next.get('title'),
                'next_subtitle': self._next.get('subtitle'),
                'next_start': self._as_datetime(self._next.get('start')),
                'next_end': self._as_datetime(self._next.get('stop')),
            })
        return attrs

    @staticmethod
    def _as_datetime(epoch):
        """Convert an epoch timestamp to an aware datetime, or None."""
        if not epoch:
            return None
        return dt_util.utc_from_timestamp(epoch)
