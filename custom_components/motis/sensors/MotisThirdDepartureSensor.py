from typing import Any

from custom_components.motis.sensors.MotisBaseSensor import MotisBaseSensor


class MotisThirdDepartureSensor(MotisBaseSensor):
    """Sensor entity for the third Motis departure.

    Tracks and exposes the third upcoming departure for a specific station, platform, and line.
    """

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Third Departure"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for the third departure sensor."""
        return super().unique_id() +  "_third"

    @property
    def state(self) -> str | None:
        """Return the ISO formatted departure time for the third upcoming departure."""
        return self._current_state_for_index(2)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes for the third departure sensor."""
        return self._current_attrs_for_index(2)
