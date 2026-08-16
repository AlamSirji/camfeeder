import json
import re

import yaml

_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_REQUIRED_FIELDS = ("id", "name", "site", "rtsp_url", "click_url")


class ConfigError(Exception):
    pass


class Camera:
    def __init__(self, id, name, site, rtsp_url, click_url, enabled=True):
        self.id = id
        self.name = name
        self.site = site
        self.rtsp_url = rtsp_url
        self.click_url = click_url
        self.enabled = enabled


def load_cameras(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML/JSON in {path}: {e}")

    if not isinstance(raw, dict) or not raw.get("cameras"):
        raise ConfigError(f"{path} must contain a non-empty top-level 'cameras' list")

    entries = raw["cameras"]
    if not isinstance(entries, list):
        raise ConfigError("'cameras' must be a list")

    cameras = []
    seen_ids = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ConfigError(f"cameras[{i}] must be a mapping")

        missing = [f for f in _REQUIRED_FIELDS if not entry.get(f)]
        if missing:
            label = entry.get("id", f"index {i}")
            raise ConfigError(f"camera '{label}' is missing required field(s): {', '.join(missing)}")

        cam_id = str(entry["id"])
        if not _ID_RE.match(cam_id):
            raise ConfigError(f"camera id '{cam_id}' is invalid; only letters, numbers, '-' and '_' are allowed")
        if cam_id in seen_ids:
            raise ConfigError(f"duplicate camera id '{cam_id}'")
        seen_ids.add(cam_id)

        cameras.append(Camera(
            id=cam_id,
            name=str(entry["name"]),
            site=str(entry["site"]),
            rtsp_url=str(entry["rtsp_url"]),
            click_url=str(entry["click_url"]),
            enabled=bool(entry.get("enabled", True)),
        ))

    return cameras


def mjpeg_stream_name(cam_id):
    return f"{cam_id}_mjpeg"


def render_go2rtc_streams_yaml(cameras):
    streams = {}
    for c in cameras:
        if not c.enabled:
            continue
        streams[c.id] = c.rtsp_url
        # Real cameras stream H.264/H.265; go2rtc's MJPEG endpoint needs an
        # explicit ffmpeg producer to transcode from the already-open source.
        streams[mjpeg_stream_name(c.id)] = f"ffmpeg:{c.id}#video=mjpeg"
    return yaml.safe_dump({"streams": streams}, default_flow_style=False)


def to_public_json(cameras):
    payload = [
        {"id": c.id, "name": c.name, "site": c.site, "click_url": c.click_url}
        for c in cameras
        if c.enabled
    ]
    return json.dumps(payload).encode("utf-8")
