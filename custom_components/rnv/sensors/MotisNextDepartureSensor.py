from typing import Any

from custom_components.rnv.sensors.MotisBaseSensor import MotisBaseSensor


class MotisNextDepartureSensor(MotisBaseSensor):
    """Sensor entity for the next Motis departure.

    Tracks and exposes the next upcoming departure for a specific station, platform, and line.
    """

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Next Departure"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for the next departure sensor."""
        return super().unique_id() +  "_next"

    @property
    def state(self) -> str | None:
        """Return the ISO formatted departure time for the next upcoming departure."""
        return self._current_state_for_index(0)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes for the next departure sensor."""
        return self._current_attrs_for_index(0)

