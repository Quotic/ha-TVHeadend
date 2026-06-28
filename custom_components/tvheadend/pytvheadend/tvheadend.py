"""
pytvheadend.tvheadend
~~~~~~~~~~~~~~~~~~~~
Provides api for TVHeadend
Copyright (c) 2019 John Mihalic <https://github.com/mezz64>
Modified by quotic <https://github.com/Quotic>
Licensed under the MIT license.
"""

import asyncio
import logging

import aiohttp

from .stream import Stream
from .constants import (
    DEFAULT_TIMEOUT, DEFAULT_HEADERS, DEFAULT_PORT,
    SUBSCRIPTIONS_URL, CHANNELS_URL, SERVICES_URL,
    __version__)

_LOGGER = logging.getLogger(__name__)


class TVHeadend(object):
    """TVHeadend API object."""

    def __init__(self, host=None, port=DEFAULT_PORT,
                 usr=None, pwd=None, maxconn=1):
        """Initialize TVHeadend class."""

        _LOGGER.debug('pyTVHeadend %s initializing new server at: %s',
                      __version__, host)

        if not host:
            _LOGGER.error('Host not specified! Cannot continue.')
            return

        self.host = host
        self.usr = usr
        self.pwd = pwd

        self.root_url = 'http://{}:{}'.format(host, port)

        self.chan_json = None
        self.serv_json = None

        self._streams = {}
        self._active_subscriptions = []

        self._ext_list = [Stream(self) for _ in range(int(maxconn))]

        self._api_session = aiohttp.ClientSession(headers=DEFAULT_HEADERS)

        self._update_callbacks = []

    @property
    def active_subscriptions(self):
        """Return list of current subscriptions."""
        return self._active_subscriptions

    @property
    def active_streams(self):
        """Return dictionary of active streams."""
        return self._streams

    @property
    def stream_list(self):
        """Return external stream list."""
        return self._ext_list

    def add_update_callback(self, callback):
        """Register as callback for when a stream changes."""
        self._update_callbacks.append(callback)
        _LOGGER.debug('Added update callback to %s', callback)

    def remove_update_callback(self, callback):
        """Remove a registered update callback."""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)
            _LOGGER.debug('Removed update callback %s', callback)

    def _do_update_callback(self, msg):
        """Call registered callback functions."""
        for callback in self._update_callbacks:
            _LOGGER.debug('Update callback %s by %s', callback, msg)
            callback(msg)

    async def start(self):
        """Start api initialization."""
        await self.fetch_channel_list()
        await self.fetch_service_list()
        return True

    async def stop(self):
        """Stop api session."""
        _LOGGER.debug('Closing tvheadend session.')
        await self._api_session.close()

    async def fetch_subscription_list(self, force=False):
        """Fetch list of active stream subscriptions."""
        streams = []

        slist = await self.api_get(self.root_url + SUBSCRIPTIONS_URL,
                                   {'start': '0', 'limit': '999999999'})
        if slist is None:
            _LOGGER.error('Unable to fetch subscriptions.')
        else:
            for chann in slist['entries']:
                try:
                    streams.append({
                        'id': chann['id'],
                        'name': chann['channel'].upper(),
                        'network': chann['service'].split('/')[1].upper(),
                    })
                except KeyError as err:
                    _LOGGER.debug('Error adding stream to list: %s', err)

        self._active_subscriptions = streams
        self.update_stream_list(streams, force)

    def next_index(self):
        """Return next available index to assign stream."""
        for index, strm in enumerate(self._ext_list):
            if not strm.channel_name:
                return index

    def update_stream_list(self, streams, force):
        """Update device list."""
        if streams is None:
            _LOGGER.error('Error updating TVHeadend streams, no data.')
            return

        active_streams = []
        for channel in streams:
            stream_name = '{}.{}'.format(channel['id'], channel['name'])
            active_streams.append(stream_name)

            if stream_name not in self._streams:
                _LOGGER.debug('New stream: %s. Adding to stream list.', stream_name)
                index = self.next_index()
                self._streams[stream_name] = index

            self._ext_list[self._streams[stream_name]].update_data(channel)
            if force:
                self._do_update_callback(self._streams[stream_name])

        tmp_strm = self._streams.copy()
        try:
            for stream, index in tmp_strm.items():
                if stream not in active_streams:
                    _LOGGER.debug('Old stream: %s. Removing from stream dict.', stream)
                    del self._streams[stream]
                    self._ext_list[index].update_data()
        except Exception as err:
            _LOGGER.debug('Caught: %s', err)

    async def fetch_channel_list(self):
        """Fetch channel list."""
        result = await self.api_get(self.root_url + CHANNELS_URL,
                                    {'start': '0', 'limit': '999999999'})
        if result is None:
            _LOGGER.error('Unable to fetch channels.')
        else:
            self.chan_json = result['entries']

    async def fetch_service_list(self):
        """Fetch service list."""
        result = await self.api_get(self.root_url + SERVICES_URL,
                                    {'start': '0', 'limit': '999999999'})
        if result is None:
            _LOGGER.error('Unable to fetch services.')
        else:
            self.serv_json = result['entries']

    def get_services(self, channel_name):
        """Return list of service IDs based on channel name."""
        if not self.chan_json:
            return

        for chan in self.chan_json:
            if chan['name'] == channel_name:
                return chan['services']

    async def api_post(self, url, params=None, data=None):
        """Make api post request."""
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                post = await self._api_session.post(
                    url, params=params, data=data)
            if post.status != 200:
                _LOGGER.error('Error posting data: %s', post.status)
                return None

            if 'text/x-json' in post.headers.get('content-type', ''):
                return await post.json(content_type='text/x-json')
            return await post.text()

        except (aiohttp.ClientError, asyncio.TimeoutError,
                ConnectionRefusedError) as err:
            _LOGGER.error('Error posting data. %s', err)
            return None

    async def api_get(self, url, params=None):
        """Make api fetch request."""
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                request = await self._api_session.get(
                    url, headers=DEFAULT_HEADERS, params=params)
            if request.status != 200:
                _LOGGER.error('Error fetching data: %s', request.status)
                return None

            if 'text/x-json' in request.headers.get('content-type', ''):
                return await request.json(content_type='text/x-json')
            return await request.text()

        except (aiohttp.ClientError, asyncio.TimeoutError,
                ConnectionRefusedError) as err:
            _LOGGER.error('Error fetching data. %s', err)
            return None

    async def api_put(self, url, data=None):
        """Make api put request."""
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                put = await self._api_session.put(
                    url, headers=DEFAULT_HEADERS, data=data)
            if put.status != 200:
                _LOGGER.error('Error putting data: %s', put.status)
                return None

            if 'text/x-json' in put.headers.get('content-type', ''):
                return await put.json(content_type='text/x-json')
            return await put.text()

        except (aiohttp.ClientError, asyncio.TimeoutError,
                ConnectionRefusedError) as err:
            _LOGGER.error('Error putting data. %s', err)
            return None
