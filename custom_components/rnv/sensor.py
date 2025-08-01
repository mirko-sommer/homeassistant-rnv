"""Sensors for RNV departures.

This module defines Home Assistant sensor entities for tracking public transport departures
from RNV stations, including next, second, and third departures, with platform and line filtering.
"""

from datetime import UTC, datetime
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CLIENT_API_URL, OAUTH_URL_TEMPLATE
from .coordinator import RNVCoordinator

_LOGGER = logging.getLogger(__name__)


class RNVBaseSensor(CoordinatorEntity[RNVCoordinator], Entity):
    """Base sensor for RNV departures.

    Handles fetching and parsing departure data for a specific station, platform, and line.
    Provides common attributes and methods for derived departure sensors.
    """

    _attr_has_entity_name = True
    _attr_device_class = "timestamp"
    _attr_icon = "mdi:bus-clock"

    def __init__(
        self,
        coordinator: RNVCoordinator,
        station_id: str,
        platform: str,
        line: str,
        departure_index: int,
    ) -> None:
        """Initialize the RNVBaseSensor."""
        super().__init__(coordinator)
        self._station_id = station_id
        self._platform = platform or ""
        self._line = line or ""
        self._departure_index = departure_index

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the RNV station sensor."""
        return DeviceInfo(
            identifiers={(self._station_id, self._platform, self._line)},
            name=f"RNV Station {self._station_id}{f' {self._platform}' if self._platform else ''}{f' {self._line}' if self._line else ''}",
            manufacturer="Rhein-Neckar-Verkehr GmbH",
            model="Live Departures",
        )

    def _extract_departure(self, index: int) -> str | None:
        """Extract the ISO formatted departure time at the given index."""
        try:
            elements = self.coordinator.data["data"]["station"]["journeys"]["elements"]
        except (KeyError, TypeError):
            return None

        now = datetime.now(UTC)
        departures = []

        for journey in elements:
            if journey.get("cancelled"):
                continue

            for stop in journey.get("stops", []):
                platform_label = stop.get("pole", {}).get("platform", {}).get("label")
                line = journey.get("line", {}).get("lineGroup", {}).get("label")

                if self._platform and platform_label != self._platform:
                    continue

                if self._line and line != self._line:
                    continue

                dep_str = stop.get("realtimeDeparture", {}).get(
                    "isoString"
                ) or stop.get("plannedDeparture", {}).get("isoString")
                if not dep_str:
                    continue

                try:
                    dep_time = datetime.fromisoformat(dep_str)
                except ValueError:
                    continue

                if dep_time > now:
                    departures.append(dep_time)

        departures.sort()
        if index is not None and index < len(departures):
            return departures[index].isoformat()
        return None

    def _extract_journey_info(self, index: int) -> dict[str, Any] | None:
        """Extract journey info with only realtime and planned times at given index."""
        try:
            elements = self.coordinator.data["data"]["station"]["journeys"]["elements"]
        except (KeyError, TypeError):
            return None

        capacity_levels = {
            "NA": "Nicht vorhanden",
            "I": "I - empty - leer",
            "II": "II - light - mittel-voll",
            "III": "III - full - voll",
        }

        now = datetime.now(UTC)
        journeys_info = []

        for journey in elements:
            if journey.get("cancelled"):
                continue

            for stop in journey.get("stops", []):
                platform_label = stop.get("pole", {}).get("platform", {}).get("label")
                line = journey.get("line", {}).get("lineGroup", {}).get("label")

                if self._platform and platform_label != self._platform:
                    continue

                if self._line and line != self._line:
                    continue

                dep_str = stop.get("realtimeDeparture", {}).get(
                    "isoString"
                ) or stop.get("plannedDeparture", {}).get("isoString")
                if not dep_str:
                    continue

                try:
                    dep_time = datetime.fromisoformat(dep_str)
                except ValueError:
                    continue

                if dep_time > now:
                    loads = journey.get("loads", [{}])
                    load_type_raw = loads[0].get("loadType")
                    load_ratio_raw = loads[0].get("ratio")

                    journey_info = {
                        "planned_time": stop.get("plannedDeparture", {}).get(
                            "isoString"
                        ),
                        "realtime_time": stop.get("realtimeDeparture", {}).get(
                            "isoString"
                        ),
                        "label": journey.get("line", {})
                        .get("lineGroup", {})
                        .get("label"),
                        "destination": stop.get("destinationLabel"),
                        "cancelled": journey.get("cancelled", False),
                        "platform": platform_label,
                        "load_ratio": f"{round(load_ratio_raw * 100)}%"
                        if isinstance(load_ratio_raw, (float, int))
                        else None,
                        "load_type": capacity_levels.get(load_type_raw),
                    }
                    journeys_info.append((dep_time, journey_info))

        journeys_info.sort(key=lambda tup: tup[0])

        if index is not None and index < len(journeys_info):
            return journeys_info[index][1]
        return None


class RNVNextDepartureSensor(RNVBaseSensor):
    """Sensor entity for the next RNV departure.

    Tracks and exposes the next upcoming departure for a specific station, platform, and line.
    """

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Next Departure"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for the next departure sensor."""
        return f"rnv_{self._station_id}{f'_{self._platform}' if self._platform else ''}{f'_{self._line}' if self._line else ''}_next"

    @property
    def state(self) -> str | None:
        """Return the ISO formatted departure time for the next upcoming departure."""
        return self._extract_departure(0)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes for the next departure sensor."""
        journey_info = self._extract_journey_info(0)
        if journey_info:
            return journey_info.copy()
        return None


class RNVNextNextDepartureSensor(RNVBaseSensor):
    """Sensor entity for the second RNV departure.

    Tracks and exposes the second upcoming departure for a specific station, platform, and line.
    """

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Second Departure"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for the second departure sensor."""
        return f"rnv_{self._station_id}{f'_{self._platform}' if self._platform else ''}{f'_{self._line}' if self._line else ''}_second"

    @property
    def state(self) -> str | None:
        """Return the ISO formatted departure time for the second upcoming departure."""
        return self._extract_departure(1)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes for the second departure sensor."""
        journey_info = self._extract_journey_info(1)
        if journey_info:
            return journey_info.copy()
        return None


class RNVNextNextNextDepartureSensor(RNVBaseSensor):
    """Sensor entity for the third RNV departure.

    Tracks and exposes the third upcoming departure for a specific station, platform, and line.
    """

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Third Departure"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for the third departure sensor."""
        return f"rnv_{self._station_id}{f'_{self._platform}' if self._platform else ''}{f'_{self._line}' if self._line else ''}_third"

    @property
    def state(self) -> str | None:
        """Return the ISO formatted departure time for the third upcoming departure."""
        return self._extract_departure(2)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes for the third departure sensor."""
        journey_info = self._extract_journey_info(2)
        if journey_info:
            return journey_info.copy()
        return None


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up RNV departure sensors from a config entry.

    Adds sensor entities for each configured station, platform, and line.

    Args:
        hass: Home Assistant instance.
        entry: Config entry containing integration data and options.
        async_add_entities: Function to add entities to Home Assistant.
    """
    at_info = entry.data.get("at_info")
    tenantid = entry.data.get("tenantid")
    options = {
        "CLIENT_API_URL": CLIENT_API_URL,
        "OAUTH_URL": OAUTH_URL_TEMPLATE.format(tenantid=tenantid),
        "CLIENT_ID": entry.data.get("clientid"),
        "CLIENT_SECRET": entry.data.get("clientsecret"),
        "RESOURCE_ID": entry.data.get("resource"),
    }

    station_data = entry.options.get("stations", [])

    entities = []
    for station in station_data:
        station_id = station["id"]
        platform = station.get("platform", "")
        line = station.get("line", "")

        coordinator = RNVCoordinator(
            hass,
            options,
            at_info,
            station_id,
            platform,
            line,
            entry,
        )
        await coordinator.async_refresh()

        entities.append(
            RNVNextDepartureSensor(
                coordinator,
                station_id,
                platform,
                line,
                departure_index=0,
            )
        )
        entities.append(
            RNVNextNextDepartureSensor(
                coordinator,
                station_id,
                platform,
                line,
                departure_index=1,
            )
        )
        entities.append(
            RNVNextNextNextDepartureSensor(
                coordinator,
                station_id,
                platform,
                line,
                departure_index=2,
            )
        )

    async_add_entities(entities)
