"""
pytvheadend.tvheadend
~~~~~~~~~~~~~~~~~~~~
Provides api for TVHeadend
Copyright (c) 2019 John Mihalic <https://github.com/mezz64>
Modified by quotic <https://github.com/Quotic>
Licensed under the MIT license.
"""

import asyncio
import hashlib
import logging
import os
import re
import time

import aiohttp
from yarl import URL

from .stream import Stream
from .constants import (
    DEFAULT_TIMEOUT, DEFAULT_HEADERS, DEFAULT_PORT,
    SUBSCRIPTIONS_URL, CHANNELS_URL, SERVICES_URL, SERVERINFO_URL,
    EPG_URL, __version__)

_LOGGER = logging.getLogger(__name__)

INVALID_AUTH = "invalid_auth"

_DIGEST_FIELD = re.compile(r'(\w+)=(?:"([^"]*)"|([^,]+))')


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

        # EPG events grouped by channel uuid, each list sorted by start time
        self._epg = {}

        self._streams = {}
        self._active_subscriptions = []

        self._ext_list = [Stream(self) for _ in range(int(maxconn))]

        # Authentication state
        self._basic_auth = None
        self._digest = None
        self._nc = 0

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

    # -- Authentication -----------------------------------------------------

    def _parse_digest_challenge(self, header):
        """Parse a WWW-Authenticate digest challenge into a dict."""
        header = header.split(' ', 1)[1] if ' ' in header else header
        params = {}
        for match in _DIGEST_FIELD.finditer(header):
            value = match.group(2) if match.group(2) is not None \
                else match.group(3)
            params[match.group(1)] = value
        self._digest = params
        self._nc = 0

    def _digest_header(self, method, uri):
        """Build a digest Authorization header for the given request."""
        params = self._digest
        realm = params.get('realm', '')
        nonce = params.get('nonce', '')
        qop = params.get('qop')
        opaque = params.get('opaque')
        algorithm = params.get('algorithm', 'MD5')

        self._nc += 1
        nc_value = '{:08x}'.format(self._nc)
        cnonce = hashlib.md5(os.urandom(8)).hexdigest()[:16]

        ha1 = hashlib.md5(
            '{}:{}:{}'.format(self.usr, realm, self.pwd or '').encode()
        ).hexdigest()
        ha2 = hashlib.md5('{}:{}'.format(method, uri).encode()).hexdigest()

        if qop:
            qop = 'auth'
            response = hashlib.md5('{}:{}:{}:{}:{}:{}'.format(
                ha1, nonce, nc_value, cnonce, qop, ha2).encode()).hexdigest()
        else:
            response = hashlib.md5(
                '{}:{}:{}'.format(ha1, nonce, ha2).encode()).hexdigest()

        parts = [
            'username="{}"'.format(self.usr),
            'realm="{}"'.format(realm),
            'nonce="{}"'.format(nonce),
            'uri="{}"'.format(uri),
            'response="{}"'.format(response),
            'algorithm={}'.format(algorithm),
        ]
        if qop:
            parts += [
                'qop={}'.format(qop),
                'nc={}'.format(nc_value),
                'cnonce="{}"'.format(cnonce),
            ]
        if opaque:
            parts.append('opaque="{}"'.format(opaque))

        return 'Digest ' + ', '.join(parts)

    async def _request(self, method, url, params=None, data=None):
        """Make a request, transparently handling basic/digest auth.

        Returns the aiohttp response object, or None on a connection error.
        """
        full = URL(url)
        if params:
            full = full.with_query(params)
        uri = full.raw_path_qs

        headers = dict(DEFAULT_HEADERS)
        if self._digest and self.usr:
            headers['Authorization'] = self._digest_header(method, uri)

        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                resp = await self._api_session.request(
                    method, str(full), data=data, headers=headers,
                    auth=self._basic_auth)

            if resp.status == 401 and self.usr:
                challenge = resp.headers.get('WWW-Authenticate', '')
                await resp.read()

                if challenge.lower().startswith('digest'):
                    self._parse_digest_challenge(challenge)
                    headers['Authorization'] = self._digest_header(method, uri)
                    async with asyncio.timeout(DEFAULT_TIMEOUT):
                        resp = await self._api_session.request(
                            method, str(full), data=data, headers=headers)
                elif challenge.lower().startswith('basic'):
                    self._basic_auth = aiohttp.BasicAuth(
                        self.usr, self.pwd or '')
                    async with asyncio.timeout(DEFAULT_TIMEOUT):
                        resp = await self._api_session.request(
                            method, str(full), data=data,
                            headers=dict(DEFAULT_HEADERS),
                            auth=self._basic_auth)

            return resp

        except (aiohttp.ClientError, asyncio.TimeoutError,
                ConnectionRefusedError) as err:
            _LOGGER.error('Error during %s request. %s', method, err)
            return None

    async def verify_connection(self):
        """Check connectivity and credentials against the server.

        Returns the server info dict on success, the string "invalid_auth"
        on a rejected login, or None if the server is unreachable.
        """
        resp = await self._request('GET', self.root_url + SERVERINFO_URL)
        if resp is None:
            return None
        if resp.status == 401:
            return INVALID_AUTH
        if resp.status != 200:
            _LOGGER.error('Unexpected status verifying connection: %s',
                          resp.status)
            return None
        try:
            return await resp.json(content_type=None)
        except (aiohttp.ClientError, ValueError) as err:
            _LOGGER.error('Error parsing server info. %s', err)
            return None

    # -- API helpers --------------------------------------------------------

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
                _LOGGER.debug('New stream: %s. Adding to stream list.',
                              stream_name)
                index = self.next_index()
                self._streams[stream_name] = index

            self._ext_list[self._streams[stream_name]].update_data(channel)
            if force:
                self._do_update_callback(self._streams[stream_name])

        tmp_strm = self._streams.copy()
        try:
            for stream, index in tmp_strm.items():
                if stream not in active_streams:
                    _LOGGER.debug('Old stream: %s. Removing from stream dict.',
                                  stream)
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

    # -- Channels & EPG -----------------------------------------------------

    @property
    def channels(self):
        """Return the list of enabled channels.

        Each entry is a dict from the channel grid (uuid, name, number,
        icon_public_url, ...). Requires fetch_channel_list() to have run.
        """
        if not self.chan_json:
            return []
        return [chan for chan in self.chan_json if chan.get('enabled', True)]

    async def fetch_epg(self):
        """Fetch the EPG event grid and cache it grouped by channel uuid."""
        result = await self.api_get(self.root_url + EPG_URL,
                                    {'start': '0', 'limit': '100000'})
        if result is None:
            _LOGGER.error('Unable to fetch EPG.')
            return

        epg = {}
        for event in result.get('entries', []):
            uuid = event.get('channelUuid')
            if uuid is None:
                continue
            epg.setdefault(uuid, []).append(event)

        for events in epg.values():
            events.sort(key=lambda evt: evt.get('start', 0))

        self._epg = epg

    def epg_now_next(self, channel_uuid):
        """Return (current, next) EPG events for a channel.

        ``current`` is the event airing now (start <= now <= stop) or None;
        ``next`` is the earliest event starting after now or None.
        """
        events = self._epg.get(channel_uuid)
        if not events:
            return None, None

        now = time.time()
        current = None
        nxt = None
        for event in events:
            start = event.get('start', 0)
            stop = event.get('stop', 0)
            if start <= now <= stop:
                current = event
            elif start > now:
                nxt = event
                break

        return current, nxt

    async def _api_call(self, method, url, params=None, data=None):
        """Make an api call and return the decoded body, or None on error."""
        resp = await self._request(method, url, params=params, data=data)
        if resp is None:
            return None
        if resp.status != 200:
            _LOGGER.error('Error on %s %s: %s', method, url, resp.status)
            return None
        try:
            return await resp.json(content_type=None)
        except (aiohttp.ClientError, ValueError):
            _LOGGER.debug('Response was not JSON, returning text.')
            return await resp.text()

    async def api_get(self, url, params=None):
        """Make api fetch request."""
        return await self._api_call('GET', url, params=params)

    async def api_post(self, url, params=None, data=None):
        """Make api post request."""
        return await self._api_call('POST', url, params=params, data=data)

    async def api_put(self, url, data=None):
        """Make api put request."""
        return await self._api_call('PUT', url, data=data)
