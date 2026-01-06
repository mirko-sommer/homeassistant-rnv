import logging
from typing import Any

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.motis.data_hub_python_client.ClientFunctions import ClientFunctions
from custom_components.motis.const import CLIENT_API_URL, STEP_USER_DATA_SCHEMA
from custom_components.motis.data_hub_python_client.MotisFunctions import MotisFunctions

_LOGGER = logging.getLogger(__name__)

class MotisHub:
    """Placeholder for OAuth2 Authentication."""

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
    ) -> None:
        """Initialize MotisHub with authentication parameters.

        Args:
            hass: Home Assistant instance.
            url: URL of the motis instance
        """
        _LOGGER.info(url);
        self.hass = hass
        self.url = normalize_url(url)

    async def authenticate(self) -> bool:
        """Authenticate with the Motis API

        Returns:
            boolean indicating whether the instance was reached
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
