# camfeeder — Camera Wall Dashboard

A single-container dashboard that shows live feeds from all your RTSP cameras
as one edge-to-edge wall, with a small overlay label on each tile showing its
site and camera number. Clicking a tile navigates to that camera's own web UI
(or any URL you configure). Built to run on a Synology NAS via Container
Manager.

Uses [go2rtc](https://github.com/AlexxIT/go2rtc) internally to pull RTSP and
re-serve it as MJPEG for the browser. go2rtc is never exposed outside the
container — the dashboard's Python server proxies each stream internally.
**Only one port (200) is published.**

Prebuilt image: [`alamsirji/camfeeder`](https://hub.docker.com/r/alamsirji/camfeeder) on Docker Hub,
tagged both `latest` and with a version number (e.g. `1.0.0`) — pin a version
in production if you want upgrades to be a deliberate choice.
Source: [github.com/AlamSirji/camfeeder](https://github.com/AlamSirji/camfeeder).

## Camera config

All cameras are defined in one file, `cameras.yml` (see `examples/cameras.yml`
for the schema). Each entry has:

- `id` — unique, slug-safe (letters/numbers/`-`/`_`)
- `name` — display name (shown as the tile's tooltip)
- `site` — shown in the tile's overlay label along with its camera number
- `rtsp_url` — the camera's RTSP stream (prefer a lower-res substream if
  available, to keep CPU load down with many cameras)
- `click_url` — where clicking the tile should navigate
- `enabled` — optional, defaults to `true`

To add a camera later: append an entry to `cameras.yml` and restart the
container. No rebuild, no re-upload.

## Configuration (environment variables)

Settable in Container Manager under the container's **Environment** tab:

| Variable | Default | Purpose |
|---|---|---|
| `CAMERAS_CONFIG` | `/config/cameras.yml` | Path to the camera list, read on container start. |
| `DASHBOARD_PORT` | `200` | Port the dashboard listens on inside the container. If you change this, also update the port mapping in Container Manager — only `200` is declared as the image's default exposed port. |

`CAMERAS_CONFIG` only changes where the app looks for the file *inside* the
container — the file still has to exist there, which normally means mapping
a host shared folder (containing `cameras.yml`) to the container path in
**Volume Settings**. "config file not found" almost always means that volume
mapping is missing, not pointed at the right folder, or the file inside it
isn't actually named `cameras.yml`.

## Build

```
docker build -t camfeeder:latest .
```

The base image (`alexxit/go2rtc`) declares `EXPOSE 1984 8554 8555` and an
anonymous `/config` volume of its own; Docker's `EXPOSE`/`VOLUME` metadata is
cumulative across layers, so without extra steps a plain build would still
advertise those on top of port `200`, and Container Manager's setup wizard
would prompt for all of them. The published image is flattened after build
to reset that metadata to just `EXPOSE 200`:

```
docker create --name flatten-tmp camfeeder:latest
docker export flatten-tmp | docker import \
  --change 'ENV CAMERAS_CONFIG=/config/cameras.yml' \
  --change 'ENV DASHBOARD_PORT=200' \
  --change 'WORKDIR /app' \
  --change 'EXPOSE 200' \
  --change 'ENTRYPOINT ["/usr/bin/python3","/app/entrypoint.py"]' \
  - camfeeder:latest
docker rm -f flatten-tmp
```

## Test locally

```
docker run --rm -p 200:200 -v <local-folder-with-cameras.yml>:/config:ro camfeeder:latest
```

Then open `http://localhost:200`.

## Deploy to Synology Container Manager

### Option A: pull from Docker Hub (recommended — fast, no transfer needed)

1. In Container Manager: **Registry** → search `alamsirji/camfeeder` → **Download**. Pick a tag — `latest` or a pinned version like `1.0.0`.
2. Create a shared folder for config, e.g. `/docker/camfeeder/config`, and put
   your `cameras.yml` in it (copy from `examples/cameras.yml` as a starting
   point).
3. Create the container from the `alamsirji/camfeeder` image:
   - **Port mapping**: `200 → 200` (this is the only port needed)
   - **Volume mapping**: `/docker/camfeeder/config` → `/config`
   - **Restart policy**: always restart
4. Start the container and browse to `http://<nas-ip>:200`.

### Option B: build locally and upload the image file

1. Export the image: `docker save camfeeder:latest -o camfeeder.tar`
2. Copy `camfeeder.tar` to the NAS (File Station or `scp`).
3. In Container Manager: **Image → Add → Add From File** → select the tar.
4. Continue from step 2 in Option A (config folder, port/volume mapping, restart policy).

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
