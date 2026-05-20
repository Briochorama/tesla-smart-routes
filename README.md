# Tesla Smart Routes

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Send saved waypoint routes to your Tesla vehicle directly from Home Assistant.

## What it does

- Stores named routes with a list of Google Maps Place IDs as waypoints
- Creates one **button** entity per route — press it to send the route to your Tesla
- Wakes the vehicle automatically if it's asleep (up to 120 s timeout with retries)
- Authenticates via Tesla's official OAuth 2 Fleet API

## Requirements

- Tesla Developer App (client ID + client secret)
- [Tesla Smart Routes Add-on](https://github.com/Briochorama/tesla-smart-routes-addon) — the VCP proxy that signs navigation commands
- Home Assistant 2026.3+

## Installation

### HACS (recommended)

1. HACS → Integrations → ⋮ → **Custom repositories**
2. Add `https://github.com/Briochorama/tesla-smart-routes` (category: **Integration**)
3. Install **Tesla Smart Routes** and restart Home Assistant

### Manual

Copy `custom_components/tesla_nav/` to your `config/custom_components/` folder and restart HA.

## Setup

1. Install and start the **Tesla Smart Routes Add-on** first (see companion repo)
2. **Settings → Devices & Services → Add Integration → Tesla Smart Routes**
3. Enter your Tesla Developer App credentials and proxy URL (`https://localhost:4443` by default)
4. Complete the OAuth 2 flow

## Adding routes

After setup, click **Add entry** next to the integration:

1. Enter a route name
2. Select your vehicle (manual VIN or HA entity whose state is the VIN)
3. Add waypoints — each waypoint needs a **label** and a **Google Maps Place ID**
4. A **button** entity appears — press it to load the route on your Tesla

### Finding Place IDs

Open Google Maps, right-click a location → the first line in the popup is the coordinates / Place ID. You can also use the [Place ID Finder](https://developers.google.com/maps/documentation/places/web-service/place-id).

## Scheduling

Use **Home Assistant automations** or **blueprints** to trigger the button at specific times or on specific days. No schedule is embedded in the integration.

## Notes

- The proxy uses a self-signed TLS certificate — this is expected; the integration sets `ssl=False` when talking to the local proxy
- Waypoint strings sent to Tesla use the format `refId:<place_id>`
- Changing a route (name, vehicle, waypoints) requires a reload of the integration to reflect in entity names

## Contributing

Issues and pull requests welcome.

## License

MIT © 2025 Basile Leyraud
