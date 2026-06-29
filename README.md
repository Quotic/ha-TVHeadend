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
- **EPG service** — `tvheadend.get_epg` returns the programme guide as response
  data (filterable by channel and time window) for scripts, templates and cards,
  without creating dozens of entities.
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

### `tvheadend.get_epg`

Return the programme guide as **response data** — no EPG entities are created.

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `channel` | no | — | Channel name (or UUID). Omit for all channels. |
| `hours` | no | `6` | How many hours ahead to include (1–168). |

Each event in the response has `channel`, `channel_number`, `title`, `subtitle`,
`description`, `start`, `end` (ISO 8601) and `genre`.

Example — show the next 6 hours for one channel:

```yaml
action: tvheadend.get_epg
data:
  channel: ZDF HD
  hours: 6
response_variable: epg
```

`epg.events` then holds the list, ready to use in a template, a script, or a
custom card. (Only channels that actually have guide data on the server return
events; configure EPG grabbers in TVHeadend to populate more.)

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

### Getting audio (go2rtc)

Broadcast audio is usually AC3, which browsers can't play and Home Assistant's
stream pipeline strips out — so `pass` often gives **video but no sound**, and
many TVHeadend builds can't transcode reliably either.

Enable **"Audio via go2rtc"** in the integration's **Configure** options. The
integration then drives **go2rtc** (bundled with Home Assistant) automatically:
for whichever channel you pick, it defines a go2rtc stream that copies the video
and transcodes only the audio to AAC/Opus, and points the camera at go2rtc's
RTSP output — so the camera gains **sound while staying switchable**, with no
manual YAML.

- Requires go2rtc (default in Home Assistant 2024.11+).
- Defaults target Home Assistant's **managed** go2rtc, whose ports are prefixed
  with a `1`: **API URL** `http://127.0.0.1:11984` and **RTSP port** `18554`.
  For a standalone go2rtc / add-on use `…:1984` and `8554`.
- If go2rtc can't be reached, the camera falls back to the direct stream
  (video only) and logs a warning.

## Credits

Originally created by [John Mihalic (mezz64)](https://github.com/mezz64).
Modernized for current Home Assistant / HACS by
[quotic](https://github.com/Quotic).
