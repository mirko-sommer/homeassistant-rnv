"""Integration for Motis public transport data."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .config_flow import MotisHub
from .const import DOMAIN
from .data_hub_python_client.ClientFunctions import ClientFunctions

_PLATFORMS = [Platform.SENSOR]

type MotisConfigEntry = ConfigEntry[MotisHub]


async def async_setup_entry(hass: HomeAssistant, entry: MotisConfigEntry) -> bool:
    """Set up Motis integration from a config entry."""
    api = MotisHub(
        hass,
        entry.data["url"],
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api

    cf = ClientFunctions(entry.data)
    entry.runtime_data = cf

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update by reloading the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MotisConfigEntry) -> bool:
    """Unload the Motis integration config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
