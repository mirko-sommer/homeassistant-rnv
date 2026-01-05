from custom_components.rnv.data_hub_python_client.ClientFunctions import ClientFunctions


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