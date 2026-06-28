# TVHeadend for Home Assistant

A custom [Home Assistant](https://www.home-assistant.io/) integration for
[TVHeadend](https://tvheadend.org/). Its primary goal is to make it easy to
switch the active tuner/service for a given channel subscription in real time,
exposing each active stream as a sensor and a switch.

Code is licensed under the MIT license.

## Features

- **UI setup** — configure via Home Assistant's *Settings → Devices & Services*,
  no YAML required.
- **Auto-discovery** — TVHeadend servers that announce themselves over the
  network (Avahi/Bonjour/zeroconf) are detected automatically and offered for
  one-click setup.
- **Authentication** — supports anonymous, Basic, and Digest auth against the
  TVHeadend HTTP API.
- **Live switching** — change the active service for a stream from the UI or via
  the `tvheadend.service_switch` service.

## Installation

### HACS (recommended)

1. Add this repository (`https://github.com/Quotic/ha-TVHeadend`) as a custom
   repository in HACS, category **Integration**.
2. Install **TVHeadend Server** from HACS.
3. Restart Home Assistant.

### Manual

Copy the `custom_components/tvheadend` folder into your Home Assistant
configuration directory's `custom_components/` folder, then restart Home
Assistant.

## Setup

### Automatic discovery

If your TVHeadend server announces itself on the network (it must be built with
Avahi support, with the Avahi daemon running and announcements enabled), it will
appear under *Settings → Devices & Services* as a **Discovered** device. Click
**Configure**, enter your username and password (leave blank for anonymous
access), adjust the port if your web interface does not use the default
(`9981`), and submit.

> **Note:** Many Docker / NAS installations do not run Avahi, so discovery may
> not fire. In that case, use manual setup below.

### Manual setup

1. Go to *Settings → Devices & Services → Add Integration*.
2. Search for **TVHeadend Server**.
3. Enter the following details:

| Field | Required | Default | Notes |
|-------|----------|---------|-------|
| Host | yes | — | IP address or hostname of the server |
| Port | yes | `9981` | TVHeadend web interface / API port |
| Username | no | — | leave blank for anonymous access |
| Password | no | — | |
| Stream slots | yes | `2` | number of concurrent stream entities to expose |

The connection (and credentials) are validated against `/api/serverinfo` before
the entry is created.

### Options

The number of **stream slots** can be changed later via the integration's
**Configure** (options) button without removing and re-adding the integration.

## Services

### `tvheadend.service_switch`

Change the active service for a given stream index.

| Field | Description | Example |
|-------|-------------|---------|
| `index` | Index of the stream | `1` |
| `target` | Target service | `SERVICE_1` |

## Credits

Originally created by [John Mihalic (mezz64)](https://github.com/mezz64).
Modernized for current Home Assistant / HACS by
[quotic](https://github.com/Quotic).
