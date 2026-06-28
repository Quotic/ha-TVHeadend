"""Constants for the TVHeadend integration."""
from datetime import timedelta

DOMAIN = "tvheadend"

DEFAULT_PORT = 9981
DEFAULT_MAXCONN = 2

CONF_MAXCONN = "maxconn"

PLATFORMS = ["sensor", "switch"]

TVH_SCAN_INTERVAL = timedelta(seconds=30)

SIGNAL_UPDATE_TVH = "tvh_update"

SERVICE_SERVICE_SWITCH = "service_switch"
ATTR_TARGET_INDEX = "index"
ATTR_TARGET_SERVICE = "target"
