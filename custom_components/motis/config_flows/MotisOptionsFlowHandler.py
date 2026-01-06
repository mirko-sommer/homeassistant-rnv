import logging
import voluptuous as vol
from homeassistant import config_entries
from custom_components.motis.data_hub_python_client.ClientFunctions import ClientFunctions
from custom_components.motis.data_hub_python_client.MotisFunctions import MotisFunctions
from homeassistant.helpers import device_registry as dr

_LOGGER = logging.getLogger(__name__)


class MotisOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler for the Motis Public Transport integration.

    Manages adding and removing stations for the integration via the options flow.
    """

    def __init__(self, config_entry) -> None:
        """Initialize the MotisOptionsFlowHandler.

        Args:
            config_entry: The configuration entry for the Motis integration.
        """
        self.found_stations = []
        self.stations = list(config_entry.options.get("stations", []))
        self.hass = None  # wird in async_step_init gesetzt

    async def async_step_init(self, user_input=None):
        """Initialize the options flow.

        Args:
            user_input: Optional user input from the options flow.

        Returns:
            The result of the next step in the options flow.
        """
        self.hass = self.hass or self._config_entry.hass
        return await self.async_step_menu()

    async def async_step_menu(self, user_input=None, errors=None):
        """Handle the menu step in the options flow.

        Presents actions to add, remove, or finish editing stations.

        Args:
            user_input: Optional user input from the options flow.

        Returns:
            The result of the next step in the options flow.
        """
        if user_input is not None:
            action = user_input["action"]
            if action == "add":
                return await self.async_step_search_station()
            if action == "remove":
                return await self.async_step_remove_station()
            if action == "finish":
                return self.async_create_entry(
                    title="Motis Stations", data={"stations": self.stations}
                )

        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(
                        {
                            "add",
                            "remove",
                            "finish",
                        }
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_search_station(self, user_input=None):
        """Handle the step to search for a station in the options flow.

        Args:
            user_input: Optional user input containing search query.

        Returns:
            The result of the next step in the options flow.
        """
        errors = {}
        if user_input is not None:
            query = user_input["search_query"]
            # get url from config entry data
            url = self.config_entry.data.get("url")
            cf = ClientFunctions(url)
            mf = MotisFunctions(cf)
            try:
                geocode_result = await mf.geocode(query)
                if geocode_result is None or len(geocode_result) == 0:
                    errors["base"] = "no_stations_found"
                else:
                    self.found_stations = geocode_result
                    return await self.async_step_select_station()
            except Exception as e:
                _LOGGER.error("Error during station search: %s", e)
                errors["base"] = "search_error"

        return self.async_show_form(
            step_id="search_station",
            data_schema=vol.Schema(
                {
                    vol.Required("search_query"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_select_station(self, user_input=None, errors=None):
        """Handle the step to select a station from search results in the options flow.

        Args:
            user_input: Optional user input specifying which station to select.
            errors: Optional dictionary of errors to display.
        """
        if user_input is not None:
            selected_index = int(user_input["selected_station"])
            selected_station = self.found_stations[selected_index]
            errors = {}
            if user_input is not None:
                new_station = {
                    "id": selected_station["id"],
                    "name": selected_station["name"],
                    "platform": user_input.get("platform", ""),
                    "line": user_input.get("line", ""),
                    "radius": user_input.get("radius", "0"),
                }
                # Prevent duplicates
                for s in self.stations:
                    if (
                            s["id"] == new_station["id"]
                            and s.get("platform", "") == new_station["platform"]
                            and s.get("line", "") == new_station["line"]
                            and s.get("radius", "0") == new_station["radius"]
                    ):
                        errors["base"] = "duplicate_station"
                        break
                if not errors:
                    self.stations.append(new_station)
                    return await self.async_step_menu()

        stations_dict = {
            str(idx): f"{s['name']} ({s['id']})"
            for idx, s in enumerate(self.found_stations)
        }

        return self.async_show_form(
            step_id="select_station",
            data_schema=vol.Schema(
                {
                    vol.Required("selected_station"): vol.In(stations_dict),
                    vol.Optional("platform", default=""): str,
                    vol.Optional("line", default=""): str,
                    vol.Required("radius", default="50"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_remove_station(self, user_input=None):
        """Handle the step to remove a station from the options flow.

        Args:
            user_input: Optional user input specifying which station to remove.

        Returns:
            The result of the next step in the options flow.
        """
        if not self.stations:
            return await self.async_step_menu()

        _LOGGER.info(self.stations)

        stations_dict = {
            str(idx): f"{s['name']} ({s['id']}) ({', '.join([v for v in (s.get('platform'), s.get('line'), s.get('radius')) if v])})"
            if s.get("platform") or s.get("line") or s.get("radius")
            else s['name'] + f"{s['id']}"
            for idx, s in enumerate(self.stations)
        }

        if user_input is not None:
            idx_to_remove = user_input["station_to_remove"]
            if idx_to_remove in stations_dict:
                station_to_remove = self.stations[int(idx_to_remove)]
                await self._remove_devices_for_station(station_to_remove["id"])

                self.stations.pop(int(idx_to_remove))
            return await self.async_step_menu()

        return self.async_show_form(
            step_id="remove_station",
            data_schema=vol.Schema(
                {
                    vol.Required("station_to_remove"): vol.In(stations_dict),
                }
            ),
        )

    async def _remove_devices_for_station(self, station_id):
        device_registry = dr.async_get(self.hass)
        for device_entry in device_registry.devices.values():
            if self.config_entry.entry_id in device_entry.config_entries:
                for identifier in device_entry.identifiers:
                    if identifier[0] == station_id:
                        device_registry.async_remove_device(device_entry.id)
                        break
