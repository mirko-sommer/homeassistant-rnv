from custom_components.motis.data_hub_python_client.ClientFunctions import ClientFunctions


class MotisFunctions:

    def __init__(self, cf: ClientFunctions) -> None:
        """Initialize MotisFunctions."""
        self.cf = cf

    async def reverse_geocode(self, latitude: float, longitude: float) -> dict | None:
        """Perform reverse geocoding to get location details from coordinates.

        :param latitude: The latitude of the location.
        :param longitude: The longitude of the location.
        :return: The JSON response as a dictionary or None if failed.
        """
        params = {
            "place": f"{latitude},{longitude}"
        }
        return await self.cf.get("v1/reverse-geocode", params=params)

    async def departures(self, stop_id: str, time: str) -> dict | None:
        """Get departures for a specific stop.

        :param stop_id: The ID of the stop.
        :param time: The time for which to get departures.
        :return: The JSON response as a dictionary or None if failed.
        """
        params = {
            "stopId": stop_id,
            "radius": 50,
            "time": time,
            "n": 10
        }
        return await self.cf.get("v5/stoptimes", params=params)

    async def geocode(self, query: str) -> dict | None:
        """Perform geocoding to get location details from a query string.

        :param query: The query string for the location.
        :return: The JSON response as a dictionary or None if failed.
        """
        params = {
            "text": query,
            "type": "STOP",
        }
        return await self.cf.get("v1/geocode", params=params)