"""Config flow for the RNV Public Transport integration."""

from __future__ import annotations

import logging
import time
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import CLIENT_API_URL, DOMAIN, OAUTH_URL_TEMPLATE
from .data_hub_python_client.ClientFunctions import ClientFunctions

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("tenantid"): str,
        vol.Required("clientid"): str,
        vol.Required("clientsecret"): str,
        vol.Required("resource"): str,
    }
)


class RnvHub:
    """Placeholder for OAuth2 Authentication."""

    def __init__(
        self,
        hass: HomeAssistant,
        tenantid: str,
        clientid: str,
        clientsecret: str,
        resource: str,
    ) -> None:
        """Initialize RnvHub with authentication parameters.

        Args:
            hass: Home Assistant instance.
            tenantid: Tenant ID for OAuth2.
            clientid: Client ID for OAuth2.
            clientsecret: Client secret for OAuth2.
            resource: Resource identifier for OAuth2.
        """
        self.hass = hass
        self.tenantid = tenantid
        self.clientid = clientid
        self.clientsecret = clientsecret
        self.resource = resource
        self.options = {
            "CLIENT_API_URL": CLIENT_API_URL,
            "OAUTH_URL": OAUTH_URL_TEMPLATE.format(tenantid=tenantid),
            "CLIENT_ID": self.clientid,
            "CLIENT_SECRET": self.clientsecret,
            "RESOURCE_ID": self.resource,
        }
        self.at_info = None
        self._reauth_entry = None  # Initialize _reauth_entry to avoid attribute error
        self._entry_data = None  # Initialize _entry_data to avoid attribute error

    async def authenticate(self) -> dict[str, Any] | None:
        """Authenticate with the RNV API and retrieve an access token.

        Returns:
            A dictionary containing authentication information if successful, or None if authentication fails.

        Logs an error if no access token is received or if an exception occurs during authentication.
        """
        cf = ClientFunctions(self.options)
        try:
            at_info = await self.hass.async_add_executor_job(cf.request_access_token)
            if not at_info or "access_token" not in at_info:
                _LOGGER.error("No access token received")
                return None
            self.at_info = at_info
        except HomeAssistantError as err:
            _LOGGER.error("Authentication failed: %s", err)
            return None
        else:
            return at_info

    def token_expired(self) -> bool:
        """Return True if the access token is expired or not available.

        Returns:
            bool: True if the token is expired or missing, False otherwise.
        """
        if not self.at_info:
            return True
        expires_on = int(self.at_info.get("expires_on", 0))
        now = int(time.time())
        return now >= expires_on

    async def get_access_token(self) -> str | None:
        """Retrieve the current access token, refreshing it if expired.

        Returns:
            The access token as a string if available, otherwise None.
        """
        if self.token_expired():
            await self.authenticate()
        if self.at_info:
            return self.at_info.get("access_token")
        return None

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle re-authentication flow."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._entry_data = entry_data
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step of the config flow.

        This method processes user input for authentication, validates it,
        and creates or updates the config entry accordingly.

        Args:
            user_input: Optional dictionary containing user-provided configuration data.

        Returns:
            A ConfigFlowResult indicating the next step or entry creation.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if hasattr(self, "_reauth_entry"):
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data=user_input | {"at_info": info["at_info"]},
                    )
                    await self.hass.config_entries.async_reload(
                        self._reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")

                return self.async_create_entry(
                    title=info["title"], data=user_input | {"at_info": info["at_info"]}
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate user input and authenticate with the RNV API.

    Args:
        hass: Home Assistant instance.
        data: Dictionary containing authentication parameters.

    Returns:
        Dictionary with integration title, authentication info, and input parameters.

    Raises:
        InvalidAuth: If authentication fails.
    """
    hub = RnvHub(
        hass, data["tenantid"], data["clientid"], data["clientsecret"], data["resource"]
    )
    at_info = await hub.authenticate()
    if at_info is None:
        raise InvalidAuth

    return {
        "title": "RNV Public Transport",
        "at_info": at_info,
        "tenantid": data["tenantid"],
        "clientid": data["clientid"],
        "clientsecret": data["clientsecret"],
        "resource": data["resource"],
    }


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RNV Public Transport."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow for user input.

        Args:
            user_input: Optional dictionary containing user-provided configuration data.

        Returns:
            A ConfigFlowResult indicating the next step or entry creation.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info["title"], data=user_input | {"at_info": info["at_info"]}
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler for the RNV integration.

        Args:
            config_entry: The configuration entry for which to get the options flow.

        Returns:
            An instance of RnvOptionsFlowHandler.
        """
        return RnvOptionsFlowHandler(config_entry)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class RnvOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler for the RNV Public Transport integration.

    Manages adding and removing stations for the integration via the options flow.
    """

    def __init__(self, config_entry) -> None:
        """Initialize the RnvOptionsFlowHandler.

        Args:
            config_entry: The configuration entry for the RNV integration.
        """
        self.stations = list(config_entry.options.get("stations", []))
        self.hass = None  # wird in async_step_init gesetzt

    async def async_step_init(self, user_input=None):
        """Initialize the options flow.

        Args:
            user_input: Optional user input from the options flow.

        Returns:
            The result of the next step in the options flow.
        """
        self.hass = self.hass or self._config_entry.hass
        return await self.async_step_menu()

    async def async_step_menu(self, user_input=None):
        """Handle the menu step in the options flow.

        Presents actions to add, remove, or finish editing stations.

        Args:
            user_input: Optional user input from the options flow.

        Returns:
            The result of the next step in the options flow.
        """
        if user_input is not None:
            action = user_input["action"]
            if action == "add":
                return await self.async_step_add_station()
            if action == "remove":
                return await self.async_step_remove_station()
            if action == "finish":
                return self.async_create_entry(
                    title="RNV Stations", data={"stations": self.stations}
                )

        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(
                        {
                            "add": "➕",
                            "remove": "🗑️",
                            "finish": "✅",
                        }
                    )
                }
            ),
        )

    async def async_step_add_station(self, user_input=None):
        """Handle the step to add a new station in the options flow.

        Args:
            user_input: Optional user input containing station details.

        Returns:
            The result of the next step in the options flow.
        """
        errors = {}
        if user_input is not None:
            new_station = {
                "id": user_input["station_id"],
                "platform": user_input.get("platform", ""),
                "line": user_input.get("line", ""),
            }
            # Prevent duplicates
            for s in self.stations:
                if (
                    s["id"] == new_station["id"]
                    and s.get("platform", "") == new_station["platform"]
                    and s.get("line", "") == new_station["line"]
                ):
                    errors["base"] = "duplicate_station"
                    break
            if not errors:
                self.stations.append(new_station)
                return await self.async_step_menu()

        return self.async_show_form(
            step_id="add_station",
            data_schema=vol.Schema(
                {
                    vol.Required("station_id"): str,
                    vol.Optional("platform", default=""): str,
                    vol.Optional("line", default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_remove_station(self, user_input=None):
        """Handle the step to remove a station from the options flow.

        Args:
            user_input: Optional user input specifying which station to remove.

        Returns:
            The result of the next step in the options flow.
        """
        if not self.stations:
            return await self.async_step_menu()

        stations_dict = {
            str(idx): f"{s['id']} ({', '.join([v for v in (s.get('platform'), s.get('line')) if v])})"
            if s.get("platform") or s.get("line")
            else f"{s['id']}"
            for idx, s in enumerate(self.stations)
        }

        if user_input is not None:
            idx_to_remove = user_input["station_to_remove"]
            if idx_to_remove in stations_dict:
                station_to_remove = self.stations[int(idx_to_remove)]
                await self._remove_devices_for_station(station_to_remove["id"])

                self.stations.pop(int(idx_to_remove))
            return await self.async_step_menu()

        return self.async_show_form(
            step_id="remove_station",
            data_schema=vol.Schema(
                {
                    vol.Required("station_to_remove"): vol.In(stations_dict),
                }
            ),
        )

    async def _remove_devices_for_station(self, station_id):
        device_registry = dr.async_get(self.hass)
        for device_entry in list(device_registry.devices.values()):
            if self.config_entry.entry_id in device_entry.config_entries:
                for identifier in device_entry.identifiers:
                    if identifier[0] == station_id:
                        device_registry.async_remove_device(device_entry.id)
                        break
