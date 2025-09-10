[![GitHub Release][releases-shield]][releases]
[![Maintainer][maintainer-shield]][maintainer]
[![HACS Custom][hacs-shield]][hacs-url]
[![GitHub Downloads][downloads]][downloads]

<img src="images/icon@2x.png" alt="RNV Logo" width="150"/>

> 🌟 This project was featured in the [official RNV Open Data Showroom (German only)](https://www.opendata-oepnv.de/ht/de/organisation/verkehrsunternehmen/rnv/openrnv/showroom?tx_news_pi1%5Baction%5D=detail&tx_news_pi1%5Bcontroller%5D=News&tx_news_pi1%5Bnews%5D=263&cHash=1e606984b7e9cb70c1d085f53b2b11f4).

# Home Assistant Rhein-Neckar-Verkehr (RNV) Integration

This custom hacs-default integration adds support for real-time public transport departures from **Rhein-Neckar-Verkehr (RNV)** to Home Assistant, using the official [RNV OpenData GraphQL API](https://www.opendata-oepnv.de/ht/de/organisation/verkehrsunternehmen/rnv/openrnv/start).

It allows you to monitor upcoming departures for RNV stations, with optional filtering by **platform** and **line**.  
Each configured station is represented as a device with separate entities for the **next three departures**.

If you find this integration useful, I’d really appreciate a ⭐️. It helps others discover it!

## Obtain API Credentials

To use this integration, you need access credentials for the RNV Open Data API.  
You can request access via the official platform here, we need the credentials for "GraphQL":  
[RNV API Access Request](https://www.opendata-oepnv.de/ht/de/organisation/verkehrsunternehmen/rnv/openrnv/api)

> Note: Approval may take a few days. Make sure to include a brief description of your use case (e.g., "For a Home Assistant integration to display upcoming public transport departures."). If you do not receive feedback within a few days, sending an email to [opendata@rnv-online.de](mailto:opendata@rnv-online.de) may help expedite the process.

Once approved, you will receive the following credentials:

- **`tenantID`**
- **`clientID`** 
- **`clientSecret`** 
- **`resource`**

You will need to enter all of these values during setup of the integration in Home Assistant.


## Installation
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mirko-sommer&repository=homeassistant-rnv&category=integration)

This integration is now available as a **default HACS repository**!

1. Install [HACS](https://hacs.xyz/) if you haven't already.
2. In HACS, go to **Integrations**.
3. Search for **RNV** and install the integration directly from the default list.
4. Restart Home Assistant if prompted.

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

## Examples
Below are two examples showing upcoming RNV public transport departures in Home Assistant:

<img src="images/example_departures.png" alt="RNV Logo" width="200"/>
<img src="images/example_betriebshof.png" alt="RNV Logo" width="250"/>

## Example Frontend Card
Using the markdown card in Home Assistant an overview like this can be generated:

<img src="images/markdown.png" alt="RNV Logo" width="300"/>

Use this code to replicate the card in Home Assistant. You only have to change the heading and your RNV sensor names:
```
type: markdown
content: |
  <h3 style="font-size: 32px; color: white;">🚏 Betriebshof</h3>

  {% set sensors = [
    'sensor.rnv_station_1144_next_departure',
    'sensor.rnv_station_1144_second_departure',
    'sensor.rnv_station_1144_third_departure'
  ] %}

  <table border="1" width="100%" cellspacing="0" cellpadding="4">
    <tr>
      <th align="center">Line</th>
      <th align="center">Destination</th>
      <th align="center">Departure</th>
      <th align="center">Platform</th>
      <th align="center">Load</th>
    </tr>
    {%- for s in sensors %}
      {%- set state = states[s] %}
      {%- if state and state.attributes.planned_time %}
        {%- set planned = as_timestamp(state.attributes.planned_time) %}
        {%- set realtime = as_timestamp(state.attributes.realtime_time) if state.attributes.realtime_time else planned %}
        {%- set departure = realtime if realtime != planned else planned %}
        {%- set minutes = ((departure - now().timestamp()) / 60) | round(0) %}
        {%- set is_rt = (realtime != planned) %}
        <tr>
          <td align="center">{{ state.attributes.label or '-' }}</td>
          <td align="center">{{ state.attributes.destination or '-' }}</td>
          <td align="center">
            {%- if is_rt %}⏱&nbsp;{%- endif %}
            {%- if minutes <= 0 -%} jetzt {%- else -%} {{ minutes }} min {%- endif -%}
          </td>
          <td align="center">{{ state.attributes.platform or '-' }}</td>
          <td align="center">{{ state.attributes.load_ratio or '-' }}</td>
        </tr>
      {%- endif %}
    {%- endfor %}
  </table>
```

For a German Version:

<img src="images/markdown_german.png" alt="RNV Logo" width="300"/>

```
type: markdown
content: |
  <h3 style="font-size: 32px; color: white;">🚏 Betriebshof</h1>

  {% set sensors = [
    'sensor.rnv_station_1144_next_departure',
    'sensor.rnv_station_1144_second_departure',
    'sensor.rnv_station_1144_third_departure'
  ] %}

  <table border="1" width="100%" cellspacing="0" cellpadding="4">
    <tr>
      <th align="center">Linie</th>
      <th align="center">Ziel</th>
      <th align="center">Abfahrt</th>
      <th align="center">Steig</th>
      <th align="center">Belegt</th>
    </tr>
    {%- for s in sensors %}
      {%- set state = states[s] %}
      {%- if state %}
        {%- set planned = as_timestamp(state.attributes.planned_time) %}
        {%- set realtime = as_timestamp(state.attributes.realtime_time) %}
        {%- set departure = realtime if realtime != planned else planned %}
        {%- set minutes = ((departure - now().timestamp()) / 60) | round(0) %}
        {%- set is_rt = (realtime != planned) %}
        <tr>
          <td align="center">{{ state.attributes.label }}</td>
          <td align="center">{{ state.attributes.destination }}</td>
          <td align="center">
            {%- if is_rt %}⏱&nbsp;{%- endif %}
            {%- if minutes <= 0 -%}
              now
            {%- else -%}
              {{ minutes }} min
            {%- endif -%}
          </td>
          <td align="center">{{ state.attributes.platform or '-' }}</td>
          <td align="center">{{ state.attributes.load_ratio or '-' }}</td>
        </tr>
      {%- endif %}
    {%- endfor %}
  </table>

```

## License

This project is licensed under the [MIT License](./LICENSE),  
based on the official [RNV OpenData Python Client](https://github.com/Rhein-Neckar-Verkehr/data-hub-python-client).

> **Disclaimer:** This project is an independent community integration and is not affiliated with or endorsed by Rhein-Neckar-Verkehr GmbH (RNV).

[releases-shield]: https://img.shields.io/github/release/mirko-sommer/homeassistant-rnv.svg?style=for-the-badge
[releases]: https://github.com/mirko-sommer/homeassistant-rnv/releases

[maintainer-shield]: https://img.shields.io/badge/maintainer-mirko--sommer-blue.svg?style=for-the-badge
[maintainer]: https://github.com/mirko-sommer

[hacs-shield]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[hacs-url]: https://github.com/mirko-sommer/homeassistant-rnv

[downloads]: https://img.shields.io/github/downloads/mirko-sommer/homeassistant-rnv/total?style=for-the-badge

