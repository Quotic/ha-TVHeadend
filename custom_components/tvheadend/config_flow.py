"""Config flow for the TVHeadend integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

try:
    # Home Assistant 2024.4+
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
except ImportError:  # pragma: no cover - older cores
    from homeassistant.components.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_MAXCONN, CONF_STREAM_PROFILE, DEFAULT_MAXCONN, DEFAULT_PORT,
    DEFAULT_STREAM_PROFILE, DOMAIN, STREAM_PROFILES)
from .pytvheadend.tvheadend import TVHeadend

_LOGGER = logging.getLogger(__name__)

RESULT_INVALID_AUTH = "invalid_auth"

ZEROCONF_SUFFIX = "._htsp._tcp.local."


async def _async_validate(host, port, username, password):
    """Try to connect to the server and return its info, or an error string.

    Returns a dict of server info on success, the string "invalid_auth" if the
    credentials were rejected, or None if the server could not be reached.
    """
    tvh = TVHeadend(host, port, usr=username, pwd=password, maxconn=1)
    try:
        return await tvh.verify_connection()
    finally:
        await tvh.stop()


class TVHeadendConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TVHeadend."""

    VERSION = 1

    def __init__(self):
        """Initialize the flow."""
        self._discovered = {}
        self._discovered_name = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step where the user enters server details."""
        errors = {}

        if user_input is not None:
            result = await self._async_validate_and_create(
                user_input, title="TVHeadend ({})".format(user_input[CONF_HOST]))
            if isinstance(result, str):
                errors["base"] = result
            else:
                return result

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo):
        """Handle a TVHeadend server discovered via zeroconf (_htsp._tcp)."""
        host = self._discovery_host(discovery_info)
        if host is None:
            return self.async_abort(reason="cannot_connect")

        self._discovered_name = self._discovery_name(discovery_info) or host

        # Key on host so a server added manually is not re-offered for discovery.
        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()

        # HTSP advertises its own port (default 9982), not the HTTP API port,
        # so fall back to the standard web UI port and let the user adjust.
        self._discovered = {CONF_HOST: host, CONF_PORT: DEFAULT_PORT}
        self.context["title_placeholders"] = {"name": self._discovered_name}

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None):
        """Confirm a discovered server and collect credentials."""
        errors = {}

        if user_input is not None:
            result = await self._async_validate_and_create(
                user_input, title=self._discovered_name)
            if isinstance(result, str):
                errors["base"] = result
            else:
                return result

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=self._user_schema(user_input or self._discovered),
            errors=errors,
            description_placeholders={"name": self._discovered_name},
        )

    async def _async_validate_and_create(self, user_input, title):
        """Validate input and create the entry, or return an error string.

        Returns a `FlowResult` (the created entry) on success, or one of the
        error keys ("cannot_connect" / "invalid_auth") on failure.
        """
        result = await _async_validate(
            user_input[CONF_HOST],
            user_input[CONF_PORT],
            user_input.get(CONF_USERNAME),
            user_input.get(CONF_PASSWORD),
        )

        if result is None:
            return "cannot_connect"
        if result == RESULT_INVALID_AUTH:
            return "invalid_auth"

        await self.async_set_unique_id(user_input[CONF_HOST])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=user_input)

    @staticmethod
    def _discovery_host(discovery_info):
        """Extract the host from a zeroconf discovery, across HA versions."""
        ip_address = getattr(discovery_info, "ip_address", None)
        if ip_address is not None:
            return str(ip_address)
        return getattr(discovery_info, "host", None)

    @staticmethod
    def _discovery_name(discovery_info):
        """Extract the friendly server name from the mDNS instance name."""
        name = getattr(discovery_info, "name", "") or ""
        if name.endswith(ZEROCONF_SUFFIX):
            return name[:-len(ZEROCONF_SUFFIX)]
        return name or None

    @staticmethod
    def _user_schema(defaults):
        """Build the form schema, pre-filled with prior or discovered input."""
        return vol.Schema({
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): cv.string,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): cv.port,
            vol.Optional(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): cv.string,
            vol.Optional(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): cv.string,
            vol.Required(CONF_MAXCONN, default=defaults.get(CONF_MAXCONN, DEFAULT_MAXCONN)):
                vol.All(vol.Coerce(int), vol.Range(min=1, max=20)),
        })

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return TVHeadendOptionsFlow(config_entry)


class TVHeadendOptionsFlow(config_entries.OptionsFlow):
    """Handle adjusting the number of stream slots after setup."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_maxconn = self.config_entry.options.get(
            CONF_MAXCONN,
            self.config_entry.data.get(CONF_MAXCONN, DEFAULT_MAXCONN),
        )
        current_profile = self.config_entry.options.get(
            CONF_STREAM_PROFILE, DEFAULT_STREAM_PROFILE)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_MAXCONN, default=current_maxconn):
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=20)),
                vol.Required(CONF_STREAM_PROFILE, default=current_profile):
                    vol.In(STREAM_PROFILES),
            }),
        )
