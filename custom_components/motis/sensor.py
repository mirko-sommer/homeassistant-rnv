"""Sensors for Motis departures.

This module defines Home Assistant sensor entities for tracking public transport departures
from Motis stations, including next, second, and third departures, with platform and line filtering.
"""

import logging
from homeassistant.core import HomeAssistant
from .coordinator import MotisCoordinator
from .sensors.MotisNextDepartureSensor import MotisNextDepartureSensor
from .sensors.MotisSecondDepartureSensor import MotisSecondDepartureSensor
from .sensors.MotisThirdDepartureSensor import MotisThirdDepartureSensor

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up Motis departure sensors from a config entry.

    Adds sensor entities for each configured station, platform, and line.

    Args:
        hass: Home Assistant instance.
        entry: Config entry containing integration data and options.
        async_add_entities: Function to add entities to Home Assistant.
    """
    at_info = entry.data.get("at_info")
    url = entry.data.get("url")

    # MIGRATION: If options are empty but stations exist in data, migrate them
    if not entry.options.get("stations") and entry.data.get("stations"):
        hass.config_entries.async_update_entry(
            entry, options={"stations": entry.data["stations"]}
        )

    # Always read stations from options
    station_data = entry.options.get("stations", [])

    entities = []
    for station in station_data:
        station_id = station["id"]
        station_name = station.get("name", "")
        platform = station.get("platform", "")
        line = station.get("line", "")
        radius = station.get("radius", 50)

        coordinator = MotisCoordinator(hass, url, at_info, station_id, station_name, platform, line, radius, entry)
        # Do not await coordinator.async_refresh() here; let it fetch in the background

        entities.append(
            MotisNextDepartureSensor(
                coordinator,
                station_id,
                station_name,
                platform,
                line,
                radius,
                departure_index=0,
            )
        )
        entities.append(
            MotisSecondDepartureSensor(
                coordinator,
                station_id,
                station_name,
                platform,
                line,
                radius,
                departure_index=1,
            )
        )
        entities.append(
            MotisThirdDepartureSensor(
                coordinator,
                station_id,
                station_name,
                platform,
                line,
                radius,
                departure_index=2,
            )
        )

    async_add_entities(entities)
