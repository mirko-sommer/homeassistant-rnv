"""Constants for the Motis Public Transport integration."""
import voluptuous as vol

DOMAIN = "motis"
CLIENT_API_URL = "https://api.transitous.org/api"
CLIENT_NAME = "HomeAssistantMotisIntegration"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional("url", default=CLIENT_API_URL): str,
    }
)
