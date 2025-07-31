"""Sensors for RNV departures.

This module defines Home Assistant sensor entities for tracking public transport departures
from RNV stations, including next, second, and third departures, with platform and line filtering.
"""

from datetime import UTC, datetime, timedelta
import logging
import time

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CLIENT_API_URL, OAUTH_URL_TEMPLATE
from .data_hub_python_client.ClientFunctions import ClientFunctions

_LOGGER = logging.getLogger(__name__)


class RNVBaseSensor(Entity):
    """Base sensor for RNV departures.

    Handles fetching and parsing departure data for a specific station, platform, and line.
    Provides common attributes and methods for derived departure sensors.
    """

    should_poll = True
    _attr_has_entity_name = True
    _attr_device_class = "timestamp"
    _attr_icon = "mdi:bus-clock"

    def __init__(
        self,
        options,
        at_info,
        tenantid,
        hass: HomeAssistant,
        station_id,
        platform,
        line,
        departure_index,
    ) -> None:
        """Initialize the RNVBaseSensor.

        Args:
            options: Dictionary of client options.
            at_info: Access token information.
            tenantid: Tenant ID for authentication.
            hass: Home Assistant instance.
            station_id: ID of the station.
            platform: Platform label (optional).
            line: Line label (optional).
            departure_index: Index of the departure to track.
        """
        self._cf = ClientFunctions(options)
        self._at_info = at_info
        self._tenantid = tenantid
        self._hass = hass
        self._station_id = station_id
        self._platform = platform or ""
        self._line = line or ""
        self._departure_index = departure_index
        self._attr_state = None
        self._options = options
        self._query_result = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the RNV station sensor."""
        return DeviceInfo(
            identifiers={(self._station_id, self._platform, self._line)},
            name=f"RNV Station {self._station_id}{f' {self._platform}' if self._platform else ''}{f' {self._line}' if self._line else ''}",
            manufacturer="Rhein-Neckar-Verkehr GmbH",
            model="Live Departures",
        )

    async def async_update(self) -> None:
        """Update the sensor with the latest departure data.

        Refreshes the access token if expired, queries the RNV API for departure information,
        and updates the sensor state with the latest results.
        Raises ConfigEntryAuthFailed if authentication fails.
        """
        expires_on = int(self._at_info.get("expires_on", 0))
        now_ts = int(time.time())
        if now_ts >= expires_on:
            new_at_info = await self._hass.async_add_executor_job(
                self._cf.request_access_token
            )
            if new_at_info and "access_token" in new_at_info:
                self._at_info = new_at_info
            else:
                _LOGGER.error("Failed to refresh access token")
                raise ConfigEntryAuthFailed("Token expired or authentication failed.")

        current_utc = (
            datetime.now(UTC)
            .replace(second=0, microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

        current_utc_offset_plus_1 = (
            (datetime.now(UTC) + timedelta(hours=1))
            .replace(second=0, microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

        query = f"""query {{
            station(id: "{self._station_id}") {{
                hafasID
                longName
                journeys(startTime: "{current_utc}", endTime: "{current_utc_offset_plus_1}", first:50) {{
                    totalCount
                    elements {{
                        ... on Journey {{
                            line {{
                                lineGroup {{
                                    label
                                }}
                            }}
                            loads(onlyHafasID: "{self._station_id}") {{
                                ratio
                                loadType
                            }}
                            cancelled
                            stops(onlyHafasID: "{self._station_id}") {{
                                plannedDeparture {{
                                    isoString
                                }}
                                realtimeDeparture {{
                                    isoString
                                }}
                                destinationLabel
                                pole {{
                                    platform {{
                                        label
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}"""

        self._query_result = await self._hass.async_add_executor_job(
            self._cf.request_query_response, query, self._at_info
        )
        # Set _attr_state here to hold the full query result for other entities to access
        self._attr_state = self._query_result

    def _extract_departure(self, index):
        try:
            elements = self._query_result["data"]["station"]["journeys"]["elements"]
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

                dep_time = datetime.fromisoformat(dep_str)
                if dep_time > now:
                    departures.append(dep_time)

        departures.sort()
        if index is not None and index < len(departures):
            return departures[index]
        return None

    def _extract_journey_info(self, index):
        """Extract journey info with only realtime and planned times at given index."""
        try:
            elements = self._query_result["data"]["station"]["journeys"]["elements"]
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

                realtime_str = stop.get("realtimeDeparture", {}).get("isoString")
                planned_str = stop.get("plannedDeparture", {}).get("isoString")
                dep_str = realtime_str or planned_str

                if not dep_str:
                    continue

                try:
                    dep_time = datetime.fromisoformat(dep_str)
                except ValueError:
                    continue

                if dep_time > now:
                    load_type_raw = journey.get("loads", [{}])[0].get("loadType")
                    load_ratio_raw = journey.get("loads", [{}])[0].get("ratio")

                    journey_info = {
                        "planned_time": planned_str,
                        "realtime_time": realtime_str,
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

        if index is not None and index < len(journeys_info):
            return journeys_info[index][1]
        return None


class RNVNextDepartureSensor(RNVBaseSensor):
    """Sensor entity for the next RNV departure.

    Tracks and exposes the next upcoming departure for a specific station, platform, and line.
    """

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Next Departure"

    @property
    def unique_id(self):
        """Return the unique ID for the next departure sensor."""
        return f"rnv_{self._station_id}{f'_{self._platform}' if self._platform else ''}{f'_{self._line}' if self._line else ''}_next"

    @property
    def state(self):
        """Return the ISO formatted departure time for the next upcoming departure."""
        departure = self._extract_departure(0)
        if departure:
            return departure.isoformat()
        return None

    @property
    def extra_state_attributes(self):
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
    def name(self):
        """Return the name of the sensor."""
        return "Second Departure"

    @property
    def unique_id(self):
        """Return the unique ID for the second departure sensor."""
        return f"rnv_{self._station_id}{f'_{self._platform}' if self._platform else ''}{f'_{self._line}' if self._line else ''}_second"

    @property
    def state(self):
        """Return the ISO formatted departure time for the second upcoming departure."""
        departure = self._extract_departure(1)
        if departure:
            return departure.isoformat()
        return None

    @property
    def extra_state_attributes(self):
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
    def name(self):
        """Return the name of the sensor."""
        return "Third Departure"

    @property
    def unique_id(self):
        """Return the unique ID for the third departure sensor."""
        return f"rnv_{self._station_id}{f'_{self._platform}' if self._platform else ''}{f'_{self._line}' if self._line else ''}_third"

    @property
    def state(self):
        """Return the ISO formatted departure time for the third upcoming departure."""
        departure = self._extract_departure(2)
        if departure:
            return departure.isoformat()
        return None

    @property
    def extra_state_attributes(self):
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
        entities.append(
            RNVNextDepartureSensor(
                options,
                at_info,
                tenantid,
                hass,
                station_id,
                platform,
                line,
                departure_index=0,
            )
        )
        entities.append(
            RNVNextNextDepartureSensor(
                options,
                at_info,
                tenantid,
                hass,
                station_id,
                platform,
                line,
                departure_index=1,
            )
        )
        entities.append(
            RNVNextNextNextDepartureSensor(
                options,
                at_info,
                tenantid,
                hass,
                station_id,
                platform,
                line,
                departure_index=2,
            )
        )

    async_add_entities(entities)
