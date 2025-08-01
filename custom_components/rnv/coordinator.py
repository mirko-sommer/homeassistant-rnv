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
    ) -> None:
        """Initialize the coordinator."""
        self._client = ClientFunctions(options)
        self._at_info = at_info
        self._station_id = station_id
        self._platform = platform
        self._line = line
        self._options = options

        # Poll every 60 seconds (cloud service minimum)
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"RNV {station_id} {platform} {line}",
            update_interval=timedelta(seconds=60),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from RNV API."""
        expires_on = int(self._at_info.get("expires_on", 0))
        now_ts = int(time.time())
        if now_ts >= expires_on:
            new_at_info = await self.hass.async_add_executor_job(
                self._client.request_access_token
            )
            if new_at_info and "access_token" in new_at_info:
                self._at_info = new_at_info
            else:
                raise UpdateFailed("Token expired or authentication failed.")

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

        try:
            data = await self.hass.async_add_executor_job(
                self._client.request_query_response, query, self._at_info
            )
        except Exception as err:
            raise UpdateFailed(f"Error fetching RNV data: {err}") from err
        else:
            return data
