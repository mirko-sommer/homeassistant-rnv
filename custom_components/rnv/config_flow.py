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

from .const import CLIENT_API_URL, DOMAIN
from .data_hub_python_client.ClientFunctions import ClientFunctions
from .data_hub_python_client.MotisFunctions import MotisFunctions

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional("url", default=CLIENT_API_URL): str,
    }
)

prefixes_by_field: dict[str, tuple[str, ...]] = {
    "url": ("url=",),
}


class InvalidCredentialFormat(HomeAssistantError):
    """Error raised when a credential contains unexpected formatting."""


def sanitize_credential(field: str, value: str) -> str:
    """Ensure credentials do not contain whitespace noise or known prefixes."""
    cleaned = value.strip()
    if not cleaned or cleaned != value:
        raise InvalidCredentialFormat

    for prefix in prefixes_by_field.get(field, ()):
        if cleaned.lower().startswith(prefix.lower()):
            raise InvalidCredentialFormat

    return cleaned


class RnvHub:
    """Placeholder for OAuth2 Authentication."""

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
    ) -> None:
        """Initialize RnvHub with authentication parameters.

        Args:
            hass: Home Assistant instance.
            tenantid: Tenant ID for OAuth2.
            clientid: Client ID for OAuth2.
            clientsecret: Client secret for OAuth2.
            resource: Resource identifier for OAuth2.
        """
        _LOGGER.info(url);
        self.hass = hass
        self.url = normalize_url(url)

    async def authenticate(self) -> bool:
        """Authenticate with the RNV API and retrieve an access token.

        Returns:
            A dictionary containing authentication information if successful, or None if authentication fails.

        Logs an error if no access token is received or if an exception occurs during authentication.
        """
        cf = ClientFunctions(self.url)
        mf = MotisFunctions(cf)
        try:
            gc_info = await mf.reverse_geocode(0,0)
            if gc_info is None:
                _LOGGER.error("No response from reverse geocode")
                return False
        except HomeAssistantError as err:
            _LOGGER.error("Authentication failed: %s", err)
            return False
        else:
            return True

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
            sanitized: dict[str, Any] = {}
            for key, raw_value in user_input.items():
                try:
                    sanitized[key] = sanitize_credential(key, raw_value)
                except InvalidCredentialFormat:
                    errors[key] = "invalid_format"

            try:
                if not errors:
                    info = await validate_input(self.hass, sanitized)
            except InvalidConfig:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info["title"], data=sanitized | {"url": info["url"]}
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

def normalize_url(url: str) -> str:
    """If input is empty or invalid, set to default URL."""
    if not url:
        return CLIENT_API_URL
    """Ensure the URL does not have trailing slashes."""
    url = url.rstrip("/")
    """Ensure the URL starts with http:// or https://"""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url

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
    hub = RnvHub(hass, data["url"])
    valid_config = await hub.authenticate()
    if not valid_config:
        raise InvalidConfig

    return {
        "title": "RNV Public Transport",
        "url": data["url"],
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
            sanitized: dict[str, Any] = {}
            for key, raw_value in user_input.items():
                try:
                    sanitized[key] = sanitize_credential(key, raw_value)
                except InvalidCredentialFormat:
                    errors[key] = "invalid_format"

            if not errors:
                try:
                    info = await validate_input(self.hass, sanitized)
                except InvalidConfig:
                    errors["base"] = "invalid_auth"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=info["title"],
                        data=sanitized | {"url": info["url"]},
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

class InvalidConfig(HomeAssistantError):
    """Error to indicate there is invalid config."""


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
                "radius": user_input.get("radius", ""),
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
