"""Shared helpers for TVHeadend entities."""
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def tvh_device_info(entry_id, tvh):
    """Return device info that groups all entities under the server."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="TVHeadend Server",
        manufacturer="TVHeadend",
        configuration_url=tvh.root_url,
    )
