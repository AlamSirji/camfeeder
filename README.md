# camfeeder — Camera Wall Dashboard

A single-container dashboard that shows live feeds from all your RTSP cameras
in a grid, grouped by site. Clicking a tile navigates to that camera's own
web UI (or any URL you configure). Built to run on a Synology NAS via
Container Manager.

Uses [go2rtc](https://github.com/AlexxIT/go2rtc) internally to pull RTSP and
re-serve it as MJPEG for the browser. go2rtc is never exposed outside the
container — the dashboard's Python server proxies each stream internally.
**Only one port (200) is published.**

## Camera config

All cameras are defined in one file, `cameras.yml` (see `examples/cameras.yml`
for the schema). Each entry has:

- `id` — unique, slug-safe (letters/numbers/`-`/`_`)
- `name` — display name
- `site` — grouping label shown as a section heading
- `rtsp_url` — the camera's RTSP stream (prefer a lower-res substream if
  available, to keep CPU load down with many cameras)
- `click_url` — where clicking the tile should navigate
- `enabled` — optional, defaults to `true`

To add a camera later: append an entry to `cameras.yml` and restart the
container. No rebuild, no re-upload.

## Build

```
docker build -t camfeeder:latest .
```

## Test locally

```
docker run --rm -p 200:200 -v <local-folder-with-cameras.yml>:/config:ro camfeeder:latest
```

Then open `http://localhost:200`.

## Deploy to Synology Container Manager

1. Export the image: `docker save camfeeder:latest -o camfeeder.tar`
2. Copy `camfeeder.tar` to the NAS (File Station or `scp`).
3. In Container Manager: **Image → Add → Add From File** → select the tar.
4. Create a shared folder for config, e.g. `/docker/camfeeder/config`, and put
   your `cameras.yml` in it (copy from `examples/cameras.yml` as a starting
   point).
5. Create the container:
   - **Port mapping**: `200 → 200` (this is the only port needed)
   - **Volume mapping**: `/docker/camfeeder/config` → `/config`
   - **Restart policy**: always restart
6. Start the container and browse to `http://<nas-ip>:200`.

## Troubleshooting

Check the container's logs in Container Manager (or `docker logs`) for:
- `cameras.yml problem: ...` — a config validation error, with the specific
  field/camera that's wrong.
- `go2rtc exited unexpectedly` — usually an RTSP connectivity issue; the whole
  container will exit and restart automatically.

go2rtc's own API isn't network-reachable by design. If you need to inspect it
directly, use an SSH session on the NAS:

```
docker exec -it <container> wget -qO- http://127.0.0.1:1984/api/streams
```

A tile can take a few seconds to start showing video after the container
(re)starts, or after being offline — go2rtc has to decode a fresh keyframe
from the camera's H.264 stream before it can produce the first JPEG frame.
Cameras with a long I-frame interval (some NVR sub-streams use 10s+) will be
slower to come up; a 1-2s I-frame interval on the camera keeps this snappy.
