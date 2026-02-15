"""Coordinator for RNV departures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .data_hub_python_client.ClientFunctions import ClientFunctions

_LOGGER = logging.getLogger(__name__)


class RNVCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch RNV departure data."""

    def __init__(
        self,
        hass: HomeAssistant,
        options: dict[str, Any],
        at_info: dict[str, Any],
        station_id: str,
        platform: str,
        line: str,
        config_entry,
        use_vrn: bool = False,
        global_id: str | None = None,
    ) -> None:
        """Initialize the coordinator."""
        self._client = ClientFunctions(options)
        self._at_info = at_info
        self._station_id = station_id
        self._platform = platform
        self._line = line
        self._options = options
        self._use_vrn = use_vrn
        self._global_id = global_id

        # Poll every 60 seconds (cloud service minimum)
        name_suffix = "RNV+VRN" if use_vrn else "RNV"
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{name_suffix} {station_id} {platform} {line}",
            update_interval=timedelta(seconds=60),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from RNV API."""
        # Refresh token if expired
        expires_on = int(self._at_info.get("expires_on", 0))
        now_ts = int(time.time())
        if now_ts >= expires_on:
            try:
                new_at_info = await self.hass.async_add_executor_job(
                    self._client.request_access_token
                )
            except Exception as err:
                # Treat token retrieval errors as transient update failures
                # so the sensor preserves its previous state
                raise UpdateFailed(
                    f"Error requesting access token for API: {err}"
                ) from err

            if new_at_info and "access_token" in new_at_info:
                self._at_info = new_at_info
            else:
                raise UpdateFailed("Token expired or authentication failed.")

        # Prepare time parameters
        now_utc = datetime.now(UTC)
        current_utc = (
            now_utc.replace(second=0, microsecond=0).isoformat().replace("+00:00", "Z")
        )
        
        # If time is between 00:00 and 04:00, set end time to plus 5 hours, else plus 2 hours
        if 0 <= now_utc.hour < 4:
            end_time = now_utc + timedelta(hours=5)
        else:
            end_time = now_utc + timedelta(hours=2)
        current_utc_offset = (
            end_time.replace(second=0, microsecond=0).isoformat().replace("+00:00", "Z")
        )

        # When VRN is enabled, query both RNV and VRN and combine results
        if self._use_vrn:
            return await self._fetch_combined_data(current_utc, current_utc_offset)
        else:
            # Only query RNV
            query = self._build_rnv_query(current_utc, current_utc_offset)
            try:
                data = await self.hass.async_add_executor_job(
                    self._client.request_query_response, query, self._at_info
                )
            except Exception as err:
                error_msg = f"Error fetching RNV data: {err}"
                _LOGGER.error(error_msg)
                raise UpdateFailed(error_msg) from err

            if data is None:
                error_msg = "No data returned from RNV API (transient error)"
                _LOGGER.warning(error_msg)
                raise UpdateFailed(error_msg)

            return data
    
    async def _fetch_combined_data(self, current_utc: str, current_utc_offset: str) -> dict[str, Any]:
        """Fetch both RNV and VRN data and combine them."""
        rnv_data = None
        vrn_data = None
        
        # Query RNV first
        rnv_query = self._build_rnv_query(current_utc, current_utc_offset)
        try:
            rnv_data = await self.hass.async_add_executor_job(
                self._client.request_query_response, rnv_query, self._at_info
            )
            if rnv_data is None:
                _LOGGER.warning("No data returned from RNV API (transient error)")
        except Exception as err:
            _LOGGER.warning("Error fetching RNV data (continuing with VRN): %s", err)
        
        # Query VRN second
        vrn_query = self._build_vrn_query(current_utc)
        try:
            vrn_data = await self.hass.async_add_executor_job(
                self._client.request_query_response, vrn_query, self._at_info
            )
            if vrn_data is None:
                _LOGGER.warning("No data returned from VRN API (transient error)")
        except Exception as err:
            _LOGGER.warning("Error fetching VRN data (continuing with RNV): %s", err)
        
        # If both failed, raise UpdateFailed
        if rnv_data is None and vrn_data is None:
            raise UpdateFailed("Both RNV and VRN queries failed")
        
        # Combine the data
        combined_data = {
            "data": {
                "station": None,
                "vrnStops": None
            }
        }
        
        # Add RNV data if available
        if rnv_data and "data" in rnv_data and "station" in rnv_data["data"]:
            combined_data["data"]["station"] = rnv_data["data"]["station"]
        
        # Add VRN data if available
        if vrn_data and "data" in vrn_data and "vrnStops" in vrn_data["data"]:
            combined_data["data"]["vrnStops"] = vrn_data["data"]["vrnStops"]
        
        return combined_data

    def _build_rnv_query(self, current_utc: str, current_utc_offset: str) -> str:
        """Build the RNV GraphQL query."""
        query = f"""query {{
            station(id: "{self._station_id}") {{
                hafasID
                longName
                journeys(startTime: "{current_utc}", endTime: "{current_utc_offset}", first:50) {{
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
                            vehicles
                        }}
                    }}
                }}
            }}
        }}"""
        return query

    def _build_vrn_query(self, current_utc: str) -> str:
        """Build the VRN GraphQL query."""
        # VRN requires globalID, not hafasID
        global_id = self._global_id or ""
        if not global_id:
            _LOGGER.error("VRN query requires a globalID, but none was provided for station %s", self._station_id)
            # Return a minimal query that will fail gracefully
            global_id = "unknown"
        
        query = f"""query VRN {{
            vrnStops(globalID: "{global_id}", time: "{current_utc}") {{
                service {{
                    type
                    vrnType
                    vrnSubType
                    name
                    description
                    notes
                    destinationLabel
                    cancelled
                    productType
                    label
                }}
                timetabledTime {{
                    isoString
                }}
                estimatedTime {{
                    isoString
                }}
                platform
            }}
        }}"""
        return query
