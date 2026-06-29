"""Constants for the TVHeadend integration."""
from datetime import timedelta

DOMAIN = "tvheadend"

DEFAULT_PORT = 9981
DEFAULT_MAXCONN = 2

CONF_MAXCONN = "maxconn"
CONF_STREAM_PROFILE = "stream_profile"
CONF_AUDIO_TRANSCODE = "audio_transcode"

DEFAULT_AUDIO_TRANSCODE = False

# 'pass' (H.264 passthrough) works on any server and plays via HA's stream
# pipeline; transcode profiles require working server-side transcoding.
DEFAULT_STREAM_PROFILE = "pass"
STREAM_PROFILES = [
    "pass",
    "webtv-h264-aac-mpegts",
    "webtv-h264-aac-matroska",
    "webtv-vp8-vorbis-webm",
]

PLATFORMS = ["camera", "select", "sensor", "switch"]

TVH_SCAN_INTERVAL = timedelta(seconds=30)

SIGNAL_UPDATE_TVH = "tvh_update"
SIGNAL_CHANNEL_SELECTED = "tvh_channel_selected_{}"

SERVICE_SERVICE_SWITCH = "service_switch"
ATTR_TARGET_INDEX = "index"
ATTR_TARGET_SERVICE = "target"

SERVICE_GET_EPG = "get_epg"
ATTR_CHANNEL = "channel"
ATTR_HOURS = "hours"
DEFAULT_EPG_HOURS = 6
