<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="custom_components/oase/brand/dark_logo@2x.png">
    <img src="custom_components/oase/brand/logo@2x.png" alt="OASE" width="360">
  </picture>
</p>

<h1 align="center">OASE for Home Assistant</h1>

Home Assistant custom integration for **OASE InScenio FM-Master Cloud** (EGC / "OASE Control")
smart garden & pond power controllers. Control the outlets, the dimmable outlet, attached
**pumps** (on/off, power, flow-control shows) and **RGB lighting** (colour, brightness, effects),
and read device diagnostics — directly from Home Assistant.

It talks to the OASE cloud over HTTPS using your OASE account email and password (Azure AD B2C),
via the [`pyoase`](https://github.com/deltasystems-pl/pyoase) library. No local network setup,
sniffing, or static IPs required.

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=deltasystems-pl&repository=ha-oase&category=integration)

Click the button above to add this repository to **HACS** in one step (then install & restart), or
follow the [manual steps](#installation) below.

> **Not affiliated with, endorsed by, or supported by OASE GmbH.** Use at your own risk.
> "OASE", "InScenio", and "FM-Master" are trademarks of their respective owners.

## Features

| Platform | Entity | Notes |
|----------|--------|-------|
| `switch` | Socket 1 / 2 / 3 | The three switchable outlets (device class *outlet*). |
| `light` | Dimmer | The dimmable outlet — on/off + brightness (0–255 ↔ dimmer value). |
| `switch` | Pump on/off | An attached pump's own on/off, independent of its outlet. |
| `number` | Pump power | Pump power as a percentage (matches the OASE app). |
| `select` | Pump show | Flow-control programs — Wild, Dynamic, Smooth, Calm, Splashy … or Off. |
| `light` | RGB 1 / 2 / 3 | Each channel of an attached RGB controller — colour, brightness, 10 effects. |
| `number` | RGB effect speed | Per-channel effect speed (configuration category). |
| `sensor` | Operating hours | Per device runtime, in hours (diagnostic). |
| `sensor` | Flow control status, Pump level, Dimmer level | Pump `fcStatus` (enum) + level; raw dimmer value. |
| `binary_sensor` | Connectivity | Gateway online + per-device connection state (diagnostic). |

Each gateway becomes a Home Assistant *device*; attached OASE devices appear as child devices
linked to their gateway, with their model name (e.g. *Expert 22000*, *RGB Controller*) and
firmware version.

## Requirements

- Home Assistant **2026.3.0** or newer.
- An **OASE Control** cloud account (the app / [oec.oase-livingwater.com](https://oec.oase-livingwater.com))
  with at least one FM-Master **Cloud** gateway paired.

## Installation

### HACS (recommended)

This integration is not (yet) in the HACS default store, so add it as a custom repository:

1. In Home Assistant, open **HACS → Integrations**.
2. Menu (⋮) → **Custom repositories**.
3. Repository: `https://github.com/deltasystems-pl/ha-oase`, category **Integration**. Add it.
4. Install **OASE**, then **restart Home Assistant**.

> Once accepted into the HACS default store, the custom-repository step is no longer needed.

### Manual

Copy `custom_components/oase/` into your Home Assistant `config/custom_components/` directory
and restart Home Assistant.

## Setup

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=oase)

1. **Settings → Devices & services → Add integration → OASE** (or use the button above).
2. Enter the **email** and **password** of your OASE Control account.
3. The integration validates the credentials against the OASE cloud and creates a device for
   each gateway on the account.

Credentials are stored in the config entry; the refresh token is persisted and rotated
automatically. If it ever becomes invalid, Home Assistant starts a **re-authentication** flow.
You can also change the stored credentials any time via the entry's **Reconfigure** option.

## Offline behaviour

The FM-Master Cloud can go offline when idle or unpowered. When it does:

- The gateway's **Connectivity** binary sensor turns *off* and remains available.
- Switch/light/other entities become **unavailable** (their last-known cached state is not
  presented as live).
- Sending a command while offline raises a clear error ("gateway is offline") instead of
  silently failing — the OASE cloud cannot reach the device to relay the command.

State is polled from the cloud every 30 seconds.

## How it works

Home Assistant → `pyoase` → OASE cloud REST API → gateway → device. Reads use
`GET /User/Inventory`; writes relay native **O-Net** packets through
`POST /Gateway/{id}/SendONetPacket`. All protocol/auth logic lives in the standalone
[`pyoase`](https://github.com/deltasystems-pl/pyoase) library. See its
[`docs/REVERSE_ENGINEERING.md`](https://github.com/deltasystems-pl/pyoase/blob/main/docs/REVERSE_ENGINEERING.md)
for the details.

## Troubleshooting

- **Invalid authentication** — double-check the email/password used in the OASE Control app.
- **Cannot connect** — a transient OASE cloud/network issue; the integration retries on the
  next poll.
- Download **diagnostics** from the integration entry (credentials, tokens, serials, and device
  ids are redacted) when reporting an issue.

## Contributing / issues

Bug reports and feature requests: <https://github.com/deltasystems-pl/ha-oase/issues>.

## License

[MIT](LICENSE).
