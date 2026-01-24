"""Sensors for RNV departures.

This module defines Home Assistant sensor entities for tracking public transport departures
from RNV stations, including next, second, and third departures, with platform and line filtering.
"""

from datetime import UTC, datetime, timedelta
import logging
from typing import Any
import re
from hashlib import sha256

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CLIENT_API_URL, OAUTH_URL_TEMPLATE
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
        platform: str,
        line: str,
        destinationLabel_filter: str, 
        departure_index: int,
    ) -> None:
        """Initialize the RNVBaseSensor."""
        super().__init__(coordinator)
        self._station_id = station_id
        self._platform = platform or ""
        self._line = line or ""
        self._destinationLabel_filter = destinationLabel_filter or ""
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
        # Keep backwards compatibility: only include filter hash when filter is present
        if self._destinationLabel_filter:
            identifiers = {(self._station_id, self._platform, self._line, "filter"+sha256(self._destinationLabel_filter.encode('utf-8')).hexdigest()[:8])}
        else:
            identifiers = {(self._station_id, self._platform, self._line)}
            
        return DeviceInfo(
            identifiers=identifiers,
            name=f"RNV Station {self._station_id}{f' {self._platform}' if self._platform else ''}{f' {self._line}' if self._line else ''}{f' {self._destinationLabel_filter}' if self._destinationLabel_filter else ''}",
            manufacturer="Rhein-Neckar-Verkehr GmbH",
            model="Live Departures",
        )
        
    def _get_desired_stops(self, journey: dict) -> dict:
        """Return journey filtered to only non-invalid anddesired stops"""

        # Filter out invalid stops (e.g., destination label contains "$")
        stops = journey.get("stops", [])
        filtered_stops = [
            s for s in stops if "$" not in s.get("destinationLabel", "")
        ]
        
        # If a destination filter is defined, apply it. 
        if self._destinationLabel_filter:
            # Filter out undesired end locations
            re_destinationLabel_filter = re.compile(self._destinationLabel_filter)
            filtered_stops = [
                s for s in filtered_stops if re_destinationLabel_filter.search(s.get("destinationLabel", ""))
            ]

        if filtered_stops is not stops:
            # Persist the filtered list back into the cached coordinator data
            # so other sensors won't see invalid entries either
            journey["stops"] = filtered_stops
        return filtered_stops

    def _extract_departure(self, index: int) -> str | None:
        """Extract the ISO formatted departure time at the given index."""
        try:
            elements = self.coordinator.data["data"]["station"]["journeys"]["elements"]
        except (KeyError, TypeError):
            return None

        now_utc = datetime.now(UTC)
        # allow departures up to RNV_DEPARTURE_VALID_MINUTES minutes in the past to account for
        # small clock skews or delays; anything older should be treated
        # as past and not considered an upcoming departure
        earliest_allowed = now_utc - timedelta(minutes=RNV_DEPARTURE_VALID_MINUTES)
        departures = []

        language = (self.hass.config.language or "en").lower()

        for journey in elements:
            filtered_stops = self._get_desired_stops(journey)
            
            for stop in filtered_stops:
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

                # Check if destination label indicates cancellation
                destination_label = stop.get("destinationLabel", "")
                cancelled = journey.get("cancelled", False)
                if destination_label.strip().lower() == "entfällt":
                    cancelled = True

                # include departures that are in the future or within the
                # allowed past window; always include cancelled services
                if dep_time >= earliest_allowed or cancelled:
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
        now_utc = datetime.now(UTC)
        earliest_allowed = now_utc - timedelta(minutes=RNV_DEPARTURE_VALID_MINUTES)
        journeys_info = []
        language = (self.hass.config.language or "en").lower()

        for journey in elements:
            filtered_stops = self._get_desired_stops(journey)
            for stop in filtered_stops:
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

                # Check if destination label indicates cancellation
                destination_label = stop.get("destinationLabel", "")
                cancelled = journey.get("cancelled", False)
                if destination_label.strip().lower() == "entfällt":
                    cancelled = True

                # include departures that are in the future or within the
                # allowed past window; always include cancelled services
                if dep_time >= earliest_allowed or cancelled:
                    loads = journey.get("loads", [{}])
                    load_type_raw = loads[0].get("loadType")
                    load_ratio_raw = loads[0].get("ratio")
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
                        "planned_time": stop.get("plannedDeparture", {}).get(
                            "isoString"
                        ),
                        "realtime_time": stop.get("realtimeDeparture", {}).get(
                            "isoString"
                        ),
                        "realtime_time_local": dep_local.strftime("%H:%M"),
                        "label": journey.get("line", {})
                        .get("lineGroup", {})
                        .get("label"),
                        "destination": stop.get("destinationLabel"),
                        "cancelled": cancelled,
                        "platform": platform_label,
                        "load_ratio": f"{round(load_ratio_raw * 100)}%"
                        if isinstance(load_ratio_raw, (float, int))
                        else None,
                        "load_type": capacity_levels.get(load_type_raw),
                        "time_until_departure": until_display,
                    }
                    journeys_info.append((dep_time, journey_info))

        journeys_info.sort(key=lambda tup: tup[0])

        if index is not None and index < len(journeys_info):
            return journeys_info[index][1]
        return None
        
    def _unique_base_id(self) -> str:
        """Return a unique base ID for derived classes to amend."""
        dst_hash ="filter"+sha256(self._destinationLabel_filter.encode('utf-8')).hexdigest()[:8]
        return f"rnv_{self._station_id}{f'_{self._platform}' if self._platform else ''}{f'_{self._line}' if self._line else ''}{f'_{dst_hash}' if self._destinationLabel_filter else ''}"


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
        return self._unique_base_id()+"_next"
        
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
        return self._unique_base_id()+"_second"

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
        return self._unique_base_id()+"_third"

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
    tenantid = entry.data.get("tenantid")
    options = {
        "CLIENT_API_URL": CLIENT_API_URL,
        "OAUTH_URL": OAUTH_URL_TEMPLATE.format(tenantid=tenantid),
        "CLIENT_ID": entry.data.get("clientid"),
        "CLIENT_SECRET": entry.data.get("clientsecret"),
        "RESOURCE_ID": entry.data.get("resource"),
    }

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
        platform = station.get("platform", "")
        line = station.get("line", "")
        destinationLabel_filter = station.get("destinationLabel_filter", "") 

        coordinator = RNVCoordinator(
            hass,
            options,
            at_info,
            station_id,
            platform,
            line,
            entry,
        )
        # Do not await coordinator.async_refresh() here; let it fetch in the background

        entities.append(
            RNVNextDepartureSensor(
                coordinator,
                station_id,
                platform,
                line,
                destinationLabel_filter, 
                departure_index=0,
            )
        )
        entities.append(
            RNVNextNextDepartureSensor(
                coordinator,
                station_id,
                platform,
                line,
                destinationLabel_filter,                 
                departure_index=1,
            )
        )
        entities.append(
            RNVNextNextNextDepartureSensor(
                coordinator,
                station_id,
                platform,
                line,
                destinationLabel_filter,             
                departure_index=2,
            )
        )


    async_add_entities(entities)
