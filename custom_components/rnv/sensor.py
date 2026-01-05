"""Sensors for RNV departures.

This module defines Home Assistant sensor entities for tracking public transport departures
from RNV stations, including next, second, and third departures, with platform and line filtering.
"""

from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CLIENT_API_URL
from .coordinator import RNVCoordinator

_LOGGER = logging.getLogger(__name__)

# Time window for valid departures (in minutes)
RNV_DEPARTURE_VALID_MINUTES = 5


class RNVBaseSensor(CoordinatorEntity[RNVCoordinator], RestoreEntity):
    """Base sensor entity for RNV departures.

    Provides common logic for extracting and restoring departure times and attributes
    for a specific station, platform, and line, supporting fallback to cached or restored state.
    """

    @property
    def available(self) -> bool:
        """Return True if the entity has a valid, cached, or recent restored state; False otherwise."""
        # Only available if the current, cached, or restored state is present and less than RNV_DEPARTURE_VALID_MINUTES in the past
        state = self._current_state_for_index(self._departure_index)
        if state is None:
            return False
        try:
            dt = datetime.fromisoformat(state)
        except ValueError:
            return False
        now = datetime.now(UTC)
        earliest_allowed = now - timedelta(minutes=RNV_DEPARTURE_VALID_MINUTES)
        return dt >= earliest_allowed

    _attr_has_entity_name = True
    _attr_device_class = "timestamp"
    _attr_icon = "mdi:bus-clock"

    def __init__(
        self,
        coordinator: RNVCoordinator,
        station_id: str,
        station_name: str,
        platform: str,
        line: str,
        departure_index: int,
    ) -> None:
        """Initialize the RNVBaseSensor."""
        super().__init__(coordinator)
        self._station_id = station_id
        self._station_name = station_name
        self._platform = platform or ""
        self._line = line or ""
        self._departure_index = departure_index
        # restored state/attributes populated in async_added_to_hass
        self._restored_state: str | None = None
        self._restored_attributes: dict[str, Any] | None = None
        # cache last valid state/attributes for error fallback
        self._last_valid_state: str | None = None
        self._last_valid_attributes: dict[str, Any] | None = None

    async def async_added_to_hass(self) -> None:
        """Restore last known state when Home Assistant starts.

        This allows the entity to keep its state across restarts until the
        coordinator fetches fresh data.
        """
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            # store raw state string and attributes for fallback
            self._restored_state = last_state.state
            # copy attributes to avoid accidental mutation
            self._restored_attributes = (
                dict(last_state.attributes) if last_state.attributes else None
            )

    def _current_state_for_index(self, index: int) -> str | None:
        """Return the current state for an index, fallback to last valid or restored state if missing.

        Only restore state if it is less than RNV_DEPARTURE_VALID_MINUTES minutes in the past.
        """
        val = self._extract_departure(index)
        if val is not None:
            # update last valid state
            self._last_valid_state = val
            return val
        # If coordinator data is missing (error), use last valid state
        if self._last_valid_state is not None:
            return self._last_valid_state
        # Check restored state age (ISO8601 string) on startup
        if self._restored_state:
            try:
                restored_dt = datetime.fromisoformat(self._restored_state)
            except ValueError:
                return None
            now = datetime.now(UTC)
            earliest_allowed = now - timedelta(minutes=RNV_DEPARTURE_VALID_MINUTES)
            if restored_dt >= earliest_allowed:
                return self._restored_state
        return None

    def _current_attrs_for_index(self, index: int) -> dict[str, Any] | None:
        """Return current extra attributes for an index, fallback to last valid or restored attributes if missing."""
        attrs = self._extract_journey_info(index)
        if attrs:
            # update last valid attributes
            self._last_valid_attributes = attrs.copy()
            return self._last_valid_attributes
        if self._last_valid_attributes is not None:
            return self._last_valid_attributes
        return self._restored_attributes

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the RNV station sensor."""
        return DeviceInfo(
            identifiers={(self._station_id, self._platform, self._line)},
            name=f"Motis Station {self._station_name} ({self._station_id}{f' {self._platform}' if self._platform else ''}{f' {self._line}' if self._line else ''})",
            manufacturer="Motis",
            model="Live Departures",
        )

    def _extract_journey_data(self) -> list[Any] | None:
        """Extract journey info with only realtime and planned times at given index."""
        try:
            elements = self.coordinator.data["stopTimes"]
        except (KeyError, TypeError):
            return None

        now_utc = datetime.now(UTC)
        earliest_allowed = now_utc - timedelta(minutes=RNV_DEPARTURE_VALID_MINUTES)
        journeys_info = []
        language = (self.hass.config.language or "en").lower()

        for stop in elements:
            place = stop.get("place", {})
            platform_label = place.get("track", "")
            line = stop.get("displayName", "")

            if self._platform and platform_label != self._platform:
                continue

            if self._line and line != self._line:
                continue

            dep_str = place.get("departure") or place.get("arrival")
            if not dep_str:
                continue

            try:
                dep_time = datetime.fromisoformat(dep_str)
            except ValueError:
                continue

            # Check if destination label indicates cancellation
            cancelled = stop.get("cancelled", False)

            # include departures that are in the future or within the
            # allowed past window; always include cancelled services
            if dep_time >= earliest_allowed or cancelled:
                dep_local = dt_util.as_local(dep_time)

                if cancelled:
                    until_display = (
                        "entfällt" if language.startswith("de") else "cancelled"
                    )
                else:
                    diff_seconds = int((dep_time - now_utc).total_seconds())
                    minutes_remaining = max(0, diff_seconds // 60)
                    if minutes_remaining >= 60:
                        until_display = dep_local.strftime("%H:%M")
                    elif minutes_remaining > 0:
                        until_display = f"{minutes_remaining} min"
                    else:
                        until_display = (
                            "sofort" if language.startswith("de") else "now"
                        )

                journey_info = {
                    "planned_time": place.get("scheduledDeparture", ""),
                    "realtime_time": place.get("departure", ""),
                    "realtime_time_local": dep_local.strftime("%H:%M"),
                    "label": stop.get("displayName", ""),
                    "destination": stop.get("headsign"),
                    "cancelled": cancelled,
                    "platform": platform_label,
                    "time_until_departure": until_display,
                    "realtime": stop.get("realTime", False),
                    "route_color": "#" + stop.get("routeColor", "ffffff"),
                    "route_text_color": "#" + stop.get("routeTextColor", "000000"),
                }
                journeys_info.append((dep_time, journey_info))

        journeys_info.sort(key=lambda tup: tup[0])
        return journeys_info


    def _extract_departure(self, index: int) -> str | None:
        """Extract the ISO formatted departure time at the given index."""
        departures = self._extract_journey_data() or []

        if index is not None and index < len(departures):
            return departures[index][0].isoformat()
        return None

    def _extract_journey_info(self, index: int) -> dict[str, Any] | None:
        journeys_info = self._extract_journey_data() or []

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
        return self._current_state_for_index(0)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes for the next departure sensor."""
        return self._current_attrs_for_index(0)


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
        return self._current_state_for_index(1)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes for the second departure sensor."""
        return self._current_attrs_for_index(1)


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
        return self._current_state_for_index(2)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes for the third departure sensor."""
        return self._current_attrs_for_index(2)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up RNV departure sensors from a config entry.

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

        coordinator = RNVCoordinator(
            hass,
            url,
            station.get("radius", 50),
            at_info,
            station_id,
            station_name,
            platform,
            line,
            entry,
        )
        # Do not await coordinator.async_refresh() here; let it fetch in the background

        entities.append(
            RNVNextDepartureSensor(
                coordinator,
                station_id,
                station_name,
                platform,
                line,
                departure_index=0,
            )
        )
        entities.append(
            RNVNextNextDepartureSensor(
                coordinator,
                station_id,
                station_name,
                platform,
                line,
                departure_index=1,
            )
        )
        entities.append(
            RNVNextNextNextDepartureSensor(
                coordinator,
                station_id,
                station_name,
                platform,
                line,
                departure_index=2,
            )
        )

    async_add_entities(entities)
