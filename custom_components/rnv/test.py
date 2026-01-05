from custom_components.rnv.data_hub_python_client.ClientFunctions import ClientFunctions
from custom_components.rnv.data_hub_python_client.MotisFunctions import MotisFunctions
import asyncio

cf = ClientFunctions("https://api.transitous.org/api")
mf = MotisFunctions(cf)

async def test_reverse_geocode():
    latitude = 0
    longitude = 0
    result = await mf.reverse_geocode(latitude, longitude)
    if result is None:
        print("Reverse geocode failed or returned no data.")
    else:
        print(result)

asyncio.run(test_reverse_geocode())