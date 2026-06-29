"""Minimal helpers for driving go2rtc to add audio transcoding.

go2rtc is bundled with Home Assistant. We define a stream whose source is an
ffmpeg pipeline that copies the channel's video and transcodes its audio to
browser-friendly codecs, then point the camera at go2rtc's RTSP output (which
carries AAC and therefore survives Home Assistant's stream pipeline with sound).
"""
import logging

from yarl import URL

_LOGGER = logging.getLogger(__name__)

RTSP_PORT = 8554


def stream_name(entry_id):
    """Return the go2rtc stream name used for a config entry."""
    return 'tvheadend_{}'.format(entry_id)


def rtsp_url(api_url, name):
    """Return the go2rtc RTSP URL for a stream, derived from the API URL host."""
    host = URL(api_url).host or '127.0.0.1'
    return 'rtsp://{}:{}/{}'.format(host, RTSP_PORT, name)


async def ensure_stream(session, api_url, name, src):
    """Define (replacing any existing) a go2rtc stream. True on success."""
    base = api_url.rstrip('/') + '/api/streams'
    try:
        # Drop any existing definition first so sources don't stack up.
        await session.delete(base, params={'src': name})
        resp = await session.put(base, params={'name': name, 'src': src})
        if resp.status == 200:
            return True
        _LOGGER.error('go2rtc returned %s adding stream %s', resp.status, name)
    except Exception as err:  # pragma: no cover - network/runtime
        _LOGGER.error('Could not reach go2rtc at %s: %s', api_url, err)
    return False


async def delete_stream(session, api_url, name):
    """Remove a go2rtc stream (best effort)."""
    base = api_url.rstrip('/') + '/api/streams'
    try:
        await session.delete(base, params={'src': name})
    except Exception:  # pragma: no cover - network/runtime
        pass
