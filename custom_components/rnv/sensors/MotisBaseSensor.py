from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from datetime import UTC, datetime, timedelta

from custom_components.rnv.coordinator import MotisCoordinator

# Time window for valid departures (in minutes)
Motis_DEPARTURE_VALID_MINUTES = 5


def _extract_until_display(dep_time: datetime, cancelled: bool, language: str) -> str:
    """Extract the display string for time until departure."""
    now_utc = datetime.now(UTC)

    if cancelled:
        return "entfällt" if language.startswith("de") else "cancelled"

    diff_seconds = int((dep_time - now_utc).total_seconds())
    minutes_remaining = max(0, diff_seconds // 60)
    if minutes_remaining >= 60:
        return dep_time.strftime("%H:%M")
    elif minutes_remaining > 0:
        return f"{minutes_remaining} min"
    else:
        return "sofort" if language.startswith("de") else "now"


class MotisBaseSensor(CoordinatorEntity[MotisCoordinator], RestoreEntity):
    """Base sensor entity for Motis departures.

    Provides common logic for extracting and restoring departure times and attributes
    for a specific station, platform, and line, supporting fallback to cached or restored state.
    """

    @property
    def available(self) -> bool:
        """Return True if the entity has a valid, cached, or recent restored state; False otherwise."""
        # Only available if the current, cached, or restored state is present and less than Motis_DEPARTURE_VALID_MINUTES in the past
        state = self._current_state_for_index(self._departure_index)
        if state is None:
            return False
        try:
            dt = datetime.fromisoformat(state)
        except ValueError:
            return False
        now = datetime.now(UTC)
        earliest_allowed = now - timedelta(minutes=Motis_DEPARTURE_VALID_MINUTES)
        return dt >= earliest_allowed

    _attr_has_entity_name = True
    _attr_device_class = "timestamp"
    _attr_icon = "mdi:bus-clock"

    def __init__(
            self,
            coordinator: MotisCoordinator,
            station_id: str,
            station_name: str,
            platform: str,
            line: str,
            radius: int,
            departure_index: int,
    ) -> None:
        """Initialize the MotisBaseSensor."""
        super().__init__(coordinator)
        self._station_id = station_id
        self._station_name = station_name
        self._platform = platform or ""
        self._line = line or ""
        self._radius = radius
        self._departure_index = departure_index
        # restored state/attributes populated in async_added_to_hass
        self._restored_state: str | None = None
        self._restored_attributes: dict[str, Any] | None = None
        # cache last valid state/attributes for error fallback
        self._last_valid_state: str | None = None
        self._last_valid_attributes: dict[str, Any] | None = None

    def unique_id(self) -> str:
        """Return the unique ID for the next departure sensor."""
        return f"motis_{self._station_name}{f'_{self._platform}' if self._platform else ''}{f'_{self._line}' if self._line else ''}_{self._station_id}"

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

        Only restore state if it is less than MOTIS_DEPARTURE_VALID_MINUTES minutes in the past.
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
            earliest_allowed = now - timedelta(minutes=Motis_DEPARTURE_VALID_MINUTES)
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
        """Return device information for the Motis station sensor."""
        return DeviceInfo(
            identifiers={(self._station_id, self._platform, self._line, self._radius)},
            name=self._get_station_name(),
            manufacturer="Motis",
            model="Live Departures",
        )

    def _get_station_name(self) -> str:
        """Return the station name from coordinator data."""
        name = f"Motis Station {self._station_name} ({self._station_id})"

        if self.platform and self._platform != "":
            name += f" – {self._platform}"

        if self._line and self._line != "":
            name += f" – '{self._line}'"

        name += f" – r:{self._radius}"

        return name

    def _check_skip_departure(self, dep_str: str, platform_label: str, line: str) -> bool:
        if self._platform and platform_label != self._platform:
            return True

        if self._line and line != self._line:
            return True

        if dep_str == "":
            return True
        return False

    def _extract_journey_data(self) -> list[Any] | None:
        """Extract journey info with only realtime and planned times at given index."""
        try:
            elements = self.coordinator.data["stopTimes"]
        except (KeyError, TypeError):
            return None

        now_utc = datetime.now(UTC)
        earliest_allowed = now_utc - timedelta(minutes=Motis_DEPARTURE_VALID_MINUTES)
        journeys_info = []
        language = (self.hass.config.language or "en").lower()

        for stop in elements:
            place = stop.get("place", {})
            platform_label = place.get("track", "")
            line = stop.get("displayName", "")
            dep_str = place.get("departure") or place.get("arrival", "")

            if self._check_skip_departure(dep_str, platform_label, line):
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

                until_display = _extract_until_display(dep_local, cancelled, language)

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
