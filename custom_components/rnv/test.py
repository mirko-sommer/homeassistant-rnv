from typing import Any

from custom_components.rnv.data_hub_python_client.ClientFunctions import ClientFunctions
from custom_components.rnv.data_hub_python_client.MotisFunctions import MotisFunctions
from datetime import UTC, datetime, timedelta
from homeassistant.util import dt as dt_util
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


async def _extract_journey_info(index: int) -> dict[str, Any] | None:
    """Extract journey info with only realtime and planned times at given index."""
    try:
        elements = await mf.departures("de-DELFI_de:08212:6218:11:11", 50)
        elements = elements["stopTimes"]
    except (KeyError, TypeError):
        return None


    _platform = None
    _line = None

    now_utc = datetime.now(UTC)
    earliest_allowed = now_utc - timedelta(minutes=RNV_DEPARTURE_VALID_MINUTES)
    journeys_info = []
    language = "en".lower()

    for stop in elements:
        place = stop.get("place", {})
        platform_label = place.get("track", "")
        line = stop.get("displayName", "")

        if _platform and platform_label != _platform:
            continue

        if _line and line != _line:
            continue

        dep_str = place.get("departure") or place.get("arrival")
        if not dep_str:
            continue

        try:
            dep_time = datetime.fromisoformat(dep_str)
        except ValueError:
            continue

        # Check if destination label indicates cancellation
        cancelled = stop.get("cancelled", False)

        # include departures that are in the future or within the
        # allowed past window; always include cancelled services
        if dep_time >= earliest_allowed or cancelled:
            dep_local = dt_util.as_local(dep_time)

            if cancelled:
                until_display = (
                    "entfällt" if language.startswith("de") else "cancelled"
                )
            else:
                diff_seconds = int((dep_time - now_utc).total_seconds())
                minutes_remaining = max(0, diff_seconds // 60)
                if minutes_remaining >= 60:
                    until_display = dep_local.strftime("%H:%M")
                elif minutes_remaining > 0:
                    until_display = f"{minutes_remaining} min"
                else:
                    until_display = (
                        "sofort" if language.startswith("de") else "now"
                    )

            journey_info = {
                "planned_time": place.get("scheduledDeparture", ""),
                "realtime_time": place.get("departure", ""),
                "realtime_time_local": dep_local.strftime("%H:%M"),
                "label": stop.get("displayName", ""),
                "destination": stop.get("headsign"),
                "cancelled": cancelled,
                "platform": platform_label,
                "time_until_departure": until_display,
            }
            journeys_info.append((dep_time, journey_info))

    journeys_info.sort(key=lambda tup: tup[0])

    if index is not None and index < len(journeys_info):
        return journeys_info[index][1]
    return None

# call _extract_journey_info for testing
async def test_extract_journey_info():
    index = 0
    result = await _extract_journey_info(index)
    if result is None:
        print("No journey info found.")
    else:
        print(result)

async def main():
    await test_reverse_geocode()
    await test_extract_journey_info()

asyncio.run(main())