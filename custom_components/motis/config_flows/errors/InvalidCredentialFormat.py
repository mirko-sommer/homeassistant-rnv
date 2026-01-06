from homeassistant.exceptions import HomeAssistantError

class InvalidCredentialFormat(HomeAssistantError):
    """Error raised when a credential contains unexpected formatting."""
