"""Coordinator for RNV departures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .data_hub_python_client.ClientFunctions import ClientFunctions
from .data_hub_python_client.MotisFunctions import MotisFunctions

_LOGGER = logging.getLogger(__name__)


class MotisCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch Motis departure data."""

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        at_info: dict[str, Any],
        station_id: str,
        station_name: str,
        platform: str,
        line: str,
        radius: int,
        config_entry
    ) -> None:
        """Initialize the coordinator."""
        self._client = MotisFunctions(ClientFunctions(url))
        self._radius = radius
        self._at_info = at_info
        self._station_id = station_id
        self._station_name = station_name
        self._platform = platform
        self._line = line
        self.station_name = ""

        # Poll every 60 seconds (cloud service minimum)
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"Motis {station_name} ({station_id}), {platform}, {line}, radius: {radius}",
            update_interval=timedelta(seconds=60),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Motis API."""
        now_utc = datetime.now(UTC)
        current_utc = (
            now_utc.replace(second=0, microsecond=0).isoformat().replace("+00:00", "Z")
        )

        try:
            _LOGGER.info("Fetching Motis data for station %s at %s and radius %s", self._station_id, current_utc, self._radius)
            data = await self._client.departures(self._station_id, current_utc)
        except Exception as err:
            # If the underlying client raised, surface as UpdateFailed so
            # the entity keeps its previous state instead of becoming unknown.
            raise UpdateFailed(f"Error fetching RNV data: {err}") from err

        # If client returned None (it logged the error), treat as transient
        # update failure so existing state is preserved.
        if data is None:
            raise UpdateFailed("No data returned from Motis API (transient error)")

        _LOGGER.debug("Motis data fetched successfully: %s", data)
        self.station_name = _extract_station_name(data)

        return data

def _extract_station_name(data) -> str:
    """Extract station name from at_info."""
    try:
        place = data.get("place", {})
        station_name = place.get("name", "")
        return station_name
    except (KeyError, TypeError):
        return ""
