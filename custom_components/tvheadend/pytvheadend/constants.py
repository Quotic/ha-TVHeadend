"""
pytvheadend.constants
~~~~~~~~~~~~~~~~~~~~
Constants list
Copyright (c) 2019 John Mihalic <https://github.com/mezz64>
Modified by quotic <https://github.com/Quotic>
Licensed under the MIT license.
"""

MAJOR_VERSION = 0
MINOR_VERSION = 5
SUB_MINOR_VERSION = 0
__version__ = '{}.{}.{}'.format(
    MAJOR_VERSION, MINOR_VERSION, SUB_MINOR_VERSION)

SERVERINFO_URL = '/api/serverinfo'
SUBSCRIPTIONS_URL = '/api/status/subscriptions'
EPG_URL = '/api/epg/events/grid'
CHANNELS_URL = '/api/channel/grid?start=0&limit=999999999'
SERVICES_URL = '/api/mpegts/service/grid?start=0&limit=999999999'
MUXES_URL = '/api/mpegts/mux/grid?start=0&limit=999999999'
PROFILES_URL = '/api/profile/list'

DEFAULT_PORT = 9981

DEFAULT_TIMEOUT = 60

DEFAULT_HEADERS = {}
