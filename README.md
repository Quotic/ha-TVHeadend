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
- **EPG Now/Next sensors** — one sensor per channel showing the current program,
  with the next program and details in its attributes.
- **Live TV camera** — a camera entity plus a channel picker (`select`) to watch
  any channel live in the Home Assistant dashboard and mobile app.

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

## EPG (Now/Next) sensors

For every **enabled** channel the integration creates one sensor, e.g.
`sensor.zdf_hd`. Its state is the title of the program **currently airing**, and
its attributes describe both the current and the next program:

| Attribute | Description |
|-----------|-------------|
| `channel` / `channel_number` | Channel name and number |
| `start` / `end` | Start and end time of the current program |
| `subtitle` / `description` | Details of the current program |
| `genre` | Raw DVB genre code(s) of the current program |
| `next_title` / `next_subtitle` | The next program |
| `next_start` / `next_end` | Start and end time of the next program |

The channel logo is shown as the sensor's picture when TVHeadend provides one.

EPG data is refreshed from the server every 15 minutes, and the current/next
program is recomputed locally every 30 seconds so the state advances at program
boundaries without extra server load.

> **Note:** A channel only shows program information if EPG data exists for it on
> the server. Channels without an EPG grabber configured (or pay-TV channels
> without guide data) will have a sensor whose state stays *unknown*. Configure
> EPG grabbers in TVHeadend to populate them, or disable the unwanted sensors in
> Home Assistant.

## Live TV (camera)

The integration adds a single **camera** entity (`camera.tvheadend`) and a
**channel picker** (`select.tvheadend_channel`). Choose a channel in the select
and the camera streams it live; the picture card shows the channel logo until you
open the live view, so simply having the card on a dashboard does **not** tie up a
tuner.

> **Each actively viewed stream uses one TVHeadend tuner**, exactly like a normal
> subscription. You cannot watch more channels at once than you have free tuners.

### Stream profile

The TVHeadend streaming profile used by the camera is selectable in the
integration's **Configure** (options) screen:

| Profile | Notes |
|---------|-------|
| `pass` (default) | Passthrough. Lowest server CPU, full quality. HD channels are H.264 and play through Home Assistant's stream pipeline. Audio is broadcast-native (often AC3) and relies on Home Assistant / go2rtc for browser playback. |
| `webtv-h264-aac-mpegts` | Transcoded H.264 + AAC. Best browser/audio compatibility, **but requires working H.264 transcoding (libx264) on the server.** |
| `webtv-h264-aac-matroska` | As above, Matroska container. |
| `webtv-vp8-vorbis-webm` | Transcoded VP8 + Vorbis; useful with go2rtc / WebRTC. |

> **Note:** Not all servers have working transcoding even when listed. If a
> transcode profile produces a black/again-failing stream, switch back to `pass`.

## Credits

Originally created by [John Mihalic (mezz64)](https://github.com/mezz64).
Modernized for current Home Assistant / HACS by
[quotic](https://github.com/Quotic).
