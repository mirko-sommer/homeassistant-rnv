"""Config flow for the Motis Public Transport integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant, callback

from custom_components.motis.config_flows.MotisHub import MotisHub

from custom_components.motis.config_flows.errors.InvalidCredentialFormat import InvalidCredentialFormat
from .config_flows.MotisOptionsFlowHandler import MotisOptionsFlowHandler
from .config_flows.errors.InvalidConfig import InvalidConfig
from .config_flows.helpers import sanitize_credential
from .const import DOMAIN, STEP_USER_DATA_SCHEMA

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Motis Instance."""

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
        """Return the options flow handler for the Motis integration.

        Args:
            config_entry: The configuration entry for which to get the options flow.

        Returns:
            An instance of MotisOptionsFlowHandler.
        """
        return MotisOptionsFlowHandler(config_entry)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate user input and authenticate with the Motis API.

    Args:
        hass: Home Assistant instance.
        data: Dictionary containing authentication parameters.

    Returns:
        Dictionary with integration title, authentication info, and input parameters.

    Raises:
        InvalidAuth: If authentication fails.
    """
    hub = MotisHub(hass, data["url"])
    valid_config = await hub.authenticate()
    if not valid_config:
        raise InvalidConfig

    return {
        "title": "Motis Instance (URL: {})".format(data["url"]),
        "url": data["url"],
    }
