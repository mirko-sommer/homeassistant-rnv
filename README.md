[![GitHub Release][releases-shield]][releases]
[![Maintainer][maintainer-shield]][maintainer]
[![HACS Custom][hacs-shield]][hacs-url]

# Home Assistant Rhein-Neckar-Verkehr (RNV) Integration

This custom integration adds support for real-time public transport departures from **Rhein-Neckar-Verkehr (RNV)** to Home Assistant, using the official [RNV OpenData GraphQL API](https://www.opendata-oepnv.de/ht/de/organisation/verkehrsunternehmen/rnv/openrnv/start).

It allows you to monitor upcoming departures for RNV stations, with optional filtering by **platform** and **line**.  
Each configured station is represented as a device with separate entities for the **next three departures**.


## Obtain API Credentials

To use this integration, you need access credentials for the RNV Open Data API.  
You can request access via the official platform here, we need the credentials for "GraphQL":  
👉 [RNV API Access Request](https://www.opendata-oepnv.de/ht/de/organisation/verkehrsunternehmen/rnv/openrnv/api)

> Note: Approval may take a few days. Make sure to include a brief description of your use case (e.g., "For a Home Assistant integration to display upcoming public transport departures.").

Once approved, you will receive the following credentials:

- **`tenantID`**
- **`clientID`** 
- **`clientSecret`** 
- **`resource`**

You will need to enter all of these values during setup of the integration in Home Assistant.


## Installation
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mirko-sommer&repository=homeassistant-rnv&category=integration)

Or follow these steps:

1. Install [HACS](https://hacs.xyz/) if you haven't already.
2. In HACS, go to **Integrations → ⋮ → Custom repositories**.
3. Add this repository as a [custom integration repository](https://hacs.xyz/docs/faq/custom_repositories):  
    - [https://github.com/mirko-sommer/homeassistant-rnv](https://github.com/mirko-sommer/homeassistant-rnv)
    - Set the category to `Integration`.
4. Restart Home Assistant.

## Configuration

After installation, add the integration to Home Assistant (Requesting the first access token may take a while):

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=rnv)

Or manually:

1. Go to **Settings → Devices & Services → + Add Integration**  
2. Search for **RNV**  
3. Follow the setup flow  
4. Enter the API credentials you obtained as described above


### Options

You can customize the integration after setup by managing stations through the options flow:

1. Go to **Settings → Devices & Services**.
2. Find **RNV Public Transport** and click the **cog (⚙️) icon** to open Options.

Inside the options menu, you can:

#### **Add a station:**  
Enter the station ID and optionally specify platform and line to monitor.  
The station ID (hafasId) can be found in a json file [here](https://www.opendata-oepnv.de/ht/de/organisation/verkehrsunternehmen/rnv/openrnv/datensaetze?id=1405&tx_vrrkit_view[dataset_name]=haltestellendaten-rnv&tx_vrrkit_view[action]=details&tx_vrrkit_view[controller]=View).

| Field        | Type   | Description                                      | Required | Default |
|--------------|--------|-------------------------------------------------|----------|---------|
| `station_id` | string | The unique identifier of the station (hafasID from json file, e.g. "1144" for "Betriebshof"). | Yes      | —       |
| `platform`   | string | Optional platform number (e.g. "A", "B", ...). | No       | (empty) |
| `line`       | string | Optional specific line to monitor at the station (e.g. "33", "24", ...). | No       | (empty) |

#### **Remove a station:**  
Select a station from your saved list to remove it (this also deletes associated devices).

#### **Save and exit:**  
Apply your changes and close the options menu.


## License

This project is licensed under the [MIT License](./LICENSE),  
based on code © 2024 Rhein-Neckar Verkehr GmbH.

Based on the official [RNV OpenData Python Client](https://github.com/Rhein-Neckar-Verkehr/data-hub-python-client).

[releases-shield]: https://img.shields.io/github/release/mirko-sommer/homeassistant-rnv.svg?style=for-the-badge
[releases]: https://github.com/mirko-sommer/homeassistant-rnv/releases

[maintainer-shield]: https://img.shields.io/badge/maintainer-mirko--sommer-blue.svg?style=for-the-badge
[maintainer]: https://github.com/mirko-sommer

[hacs-shield]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[hacs-url]: https://github.com/mirko-sommer/homeassistant-rnv
