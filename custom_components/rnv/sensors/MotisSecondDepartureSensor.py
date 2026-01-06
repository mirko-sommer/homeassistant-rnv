from typing import Any

from custom_components.rnv.sensors.MotisBaseSensor import MotisBaseSensor


class MotisSecondDepartureSensor(MotisBaseSensor):
    """Sensor entity for the second Motis departure.

    Tracks and exposes the second upcoming departure for a specific station, platform, and line.
    """

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Second Departure"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for the second departure sensor."""
        return super().unique_id() +  "_second"

    @property
    def state(self) -> str | None:
        """Return the ISO formatted departure time for the second upcoming departure."""
        return self._current_state_for_index(1)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes for the second departure sensor."""
        return self._current_attrs_for_index(1)
