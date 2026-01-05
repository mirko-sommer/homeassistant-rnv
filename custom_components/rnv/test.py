from typing import Any

from custom_components.rnv.data_hub_python_client.ClientFunctions import ClientFunctions
from custom_components.rnv.data_hub_python_client.MotisFunctions import MotisFunctions
import asyncio

cf = ClientFunctions("https://api.transitous.org/api")
mf = MotisFunctions(cf)
RNV_DEPARTURE_VALID_MINUTES = 5

async def test_reverse_geocode():
    latitude = 0
    longitude = 0
    result = await mf.reverse_geocode(latitude, longitude)
    if result is None:
        print("Reverse geocode failed or returned no data.")
    else:
        print(result)

async def test_geocode():
    query = "Heidelberg Hbf"
    result = await mf.geocode(query)
    if result is None:
        print("Geocode failed or returned no data.")
    else:
        print(result)


async def main():
    await test_reverse_geocode()
    await test_geocode()

asyncio.run(main())