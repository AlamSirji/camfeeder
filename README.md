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
tagged both `latest` and with a version number (e.g. `1.1.0`) — pin a version
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

## Configuration

There are no environment variables to set — the image is fixed at build
time to listen on port `200` and read its camera list from `/config/cameras.yml`
inside the container. The only thing you configure per-deployment is *where
on the NAS* that `/config` path is backed by: pick any shared folder you like
(it doesn't need to be named "config") and add it under **Volume Settings**
when creating the container, mapped to the container path `/config` — the
same manual step as mapping Kerberos.io's config/recordings folders, just
one folder instead of two since this app doesn't record anything. "config
file not found" means that mapping wasn't added, points at the wrong folder,
or the file inside it isn't actually named `cameras.yml`.

## Build

```
docker build -t camfeeder:latest .
```

The base image (`alexxit/go2rtc`) declares its own `EXPOSE 1984 8554 8555`;
Docker's `EXPOSE` metadata is cumulative across layers, so without extra
steps a plain build would still advertise those on top of port `200`, and
Container Manager's setup wizard would prompt for port mappings for all of
them. The published image is flattened after build to reset that to just
`EXPOSE 200` (keeping our own intentional `VOLUME ["/config"]` so the image
still declares that path, even though mapping a folder to it in Container
Manager is always a manual step regardless):

```
docker create --name flatten-tmp camfeeder:latest
docker export flatten-tmp | docker import \
  --change 'WORKDIR /app' \
  --change 'EXPOSE 200' \
  --change 'VOLUME ["/config"]' \
  --change 'ENTRYPOINT ["/usr/bin/python3","/app/entrypoint.py"]' \
  - camfeeder:latest
docker rm -f flatten-tmp
```

## Test locally

```
docker run --rm -p 200:200 -v <local-folder-with-cameras.yml>:/config camfeeder:latest
```

Then open `http://localhost:200`.

## Deploy to Synology Container Manager

### Option A: pull from Docker Hub (recommended — fast, no transfer needed)

1. In Container Manager: **Registry** → search `alamsirji/camfeeder` → **Download**. Pick a tag — `latest` or a pinned version like `1.1.0`.
2. Create a shared folder for config — any name/location you like, e.g.
   `docker/camfeeder/config` — and put your `cameras.yml` in it (copy from
   `examples/cameras.yml` as a starting point).
3. Create the container from the `alamsirji/camfeeder` image:
   - **Volume Settings**: click **Add Folder**, choose the folder from step 2,
     and set its mount path to `/config` (you have to add this yourself —
     it's not automatic)
   - **Port mapping**: `200 → 200` (this is the only port needed)
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
