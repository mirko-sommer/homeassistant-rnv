from __future__ import annotations

import json
import logging
import os
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class StationDataHelper:
    """Helper class for accessing station data from stations.json."""

    _data_cache: dict[str, Any] | None = None
    _cache_file_path: str | None = None

    @classmethod
    def _get_stops_file_path(cls) -> str:
        """Get the path to the stations.json file.
        
        Returns:
            Absolute path to stations.json
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, "data", "stations.json")

    @classmethod
    def _load_data_sync(cls) -> dict[str, Any]:
        """Synchronously load station data from stations.json.
        
        This is a helper method that should only be called from an executor.
        
        Returns:
            Parsed JSON data from stations.json
            
        Raises:
            Exception: If file cannot be read or parsed
        """
        stops_file = cls._get_stops_file_path()
        with open(stops_file, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    async def _load_data(cls, hass: HomeAssistant) -> dict[str, Any]:
        """Load station data from stations.json with caching.
        
        Args:
            hass: Home Assistant instance
        
        Returns:
            Parsed JSON data from stations.json
            
        Raises:
            Exception: If file cannot be read or parsed
        """
        stops_file = cls._get_stops_file_path()
        
        # Use cache if available and file path hasn't changed
        if cls._data_cache is not None and cls._cache_file_path == stops_file:
            return cls._data_cache
        
        # Run blocking file I/O in executor
        data = await hass.async_add_executor_job(cls._load_data_sync)
        cls._data_cache = data
        cls._cache_file_path = stops_file
        return cls._data_cache

    @classmethod
    async def _get_station_by_id(cls, hass: HomeAssistant, station_id: str) -> dict[str, Any] | None:
        """Get station data for a given station ID.
        
        Args:
            hass: Home Assistant instance
            station_id: The station ID to look up
            
        Returns:
            Station dictionary if found, None otherwise
        """
        try:
            data = await cls._load_data(hass)
            for station in data.get("stations", []):
                if station.get("id") == station_id:
                    return station
            return None
        except Exception as err:
            _LOGGER.debug("Error loading station data for %s: %s", station_id, err)
            return None

    @classmethod
    async def load_station_data(cls, hass: HomeAssistant) -> dict[str, str]:
        """Load station data for display in dropdown menus.
        
        Args:
            hass: Home Assistant instance
        
        Returns:
            Dictionary with station_id as key and formatted station name as value.
        """
        try:
            data = await cls._load_data(hass)
            
            # Collect stations with valid ID and name
            valid_stations = []
            for station in data.get("stations", []):
                station_id = station.get("id")
                station_name = station.get("name")
                if station_id and station_name:
                    valid_stations.append((station_id, station_name))
            
            # Sort stations alphabetically by name
            valid_stations.sort(key=lambda x: x[1].lower())
            
            # Create sorted dictionary
            stations = {}
            for station_id, station_name in valid_stations:
                # Format: "Station Name (ID: 1234)"
                display_name = f"{station_name} (ID: {station_id})"
                stations[station_id] = display_name
            
            return stations
        except Exception as err:
            _LOGGER.error("Error loading station data: %s", err)
            return {}

    @classmethod
    def get_station_name_cached(cls, station_id: str) -> str | None:
        """Get station name from cache only (non-blocking).
        
        Args:
            station_id: The station ID to look up
            
        Returns:
            Station name if found in cache, otherwise None
        """
        if cls._data_cache is None:
            return None
        
        try:
            for station in cls._data_cache.get("stations", []):
                if station.get("id") == station_id:
                    return station.get("name")
        except Exception as err:
            _LOGGER.debug("Error reading cached station name for %s: %s", station_id, err)
        
        return None
    
    @classmethod
    async def get_station_name(cls, hass: HomeAssistant, station_id: str) -> str:
        """Get station name for a given station ID.
        
        Args:
            hass: Home Assistant instance
            station_id: The station ID to look up
            
        Returns:
            Station name if found, otherwise the station ID
        """
        try:
            station = await cls._get_station_by_id(hass, station_id)
            if station:
                return station.get("name", station_id)
            return station_id
        except Exception as err:
            _LOGGER.debug("Error loading station name for %s: %s", station_id, err)
            return station_id

    @classmethod
    async def get_station_global_id(cls, hass: HomeAssistant, station_id: str) -> str | None:
        """Get global ID for a given station ID.
        
        Args:
            hass: Home Assistant instance
            station_id: The station ID (hafasID) to look up
            
        Returns:
            Global ID if found, otherwise None
        """
        try:
            station = await cls._get_station_by_id(hass, station_id)
            if station:
                return station.get("globalID")
            return None
        except Exception as err:
            _LOGGER.debug("Error loading global ID for %s: %s", station_id, err)
            return None

    @classmethod
    async def get_station_location(cls, hass: HomeAssistant, station_id: str) -> dict[str, float] | None:
        """Get location (latitude and longitude) for a given station ID.
        
        Args:
            hass: Home Assistant instance
            station_id: The station ID (hafasID) to look up
            
        Returns:
            Dict with 'latitude' and 'longitude' keys if found, otherwise None
        """
        try:
            station = await cls._get_station_by_id(hass, station_id)
            if station:
                poles = station.get("poles", [])
                if poles and len(poles) > 0:
                    location = poles[0].get("location")
                    if location:
                        return {
                            "latitude": location.get("lat"),
                            "longitude": location.get("long")
                        }
            return None
        except Exception as err:
            _LOGGER.debug("Error loading location for %s: %s", station_id, err)
            return None
