import logging
import shutil
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
GO2RTC_API = "http://127.0.0.1:1984"

log = logging.getLogger("server")

# Tracks each camera's last known state, so we only log a transition
# (up -> down, down -> up) instead of once per 5s browser retry.
_stream_state = {}


class StreamUnavailable(Exception):
    pass


def open_camera_stream(cam_id, timeout=20):
    """Open go2rtc's MJPEG endpoint for a camera and confirm a real frame is
    flowing before returning. Raises StreamUnavailable on any failure.
    Caller is responsible for closing the returned upstream response."""
    try:
        # go2rtc's ffmpeg-based MJPEG transcoder can't produce a frame for a
        # new consumer until it decodes a keyframe from the RTSP source, so
        # this can take a few seconds on cameras with a long GOP/I-frame
        # interval. Keep this generous.
        upstream = urllib.request.urlopen(
            f"{GO2RTC_API}/api/stream.mjpeg?src={cam_id}_mjpeg", timeout=timeout
        )
        # go2rtc answers 200 immediately even if the RTSP source never
        # connects, then just closes the body with no data once its internal
        # dial times out. Confirm a real frame is coming before trusting the
        # connection, so a dead camera is reported as unavailable rather than
        # as a silent, empty 200.
        first_chunk = upstream.read(4096)
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise StreamUnavailable(str(e)) from e

    if not first_chunk:
        upstream.close()
        raise StreamUnavailable("no data received")

    return upstream, first_chunk


def mark_stream_result(cam_id, ok, detail=""):
    state = "up" if ok else "down"
    if _stream_state.get(cam_id) == state:
        return
    _stream_state[cam_id] = state
    if ok:
        log.info("camera %s: stream connected", cam_id)
    else:
        log.warning("camera %s: stream unavailable (%s)", cam_id, detail)


def build_handler(cameras_json, known_ids):
    class Handler(BaseHTTPRequestHandler):
        server_version = "camfeeder/1.0"

        def log_message(self, fmt, *args):
            # Silence the default per-request access log (every static
            # asset load and every stream retry) — noise, not diagnostics.
            pass

        def do_GET(self):
            if self.path == "/api/cameras":
                self._send_bytes(cameras_json, "application/json")
            elif self.path.startswith("/stream/"):
                self._proxy_stream(self.path[len("/stream/"):])
            else:
                self._serve_static()

        def _send_bytes(self, body, content_type):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _proxy_stream(self, cam_id):
            cam_id = cam_id.split("?")[0]
            if cam_id not in known_ids:
                log.warning("stream request for unknown camera id %r", cam_id)
                self.send_error(404, "unknown camera id")
                return

            try:
                upstream, first_chunk = open_camera_stream(cam_id)
            except StreamUnavailable as e:
                mark_stream_result(cam_id, ok=False, detail=str(e))
                self.send_error(502, "camera stream unavailable")
                return

            mark_stream_result(cam_id, ok=True)
            try:
                self.send_response(200)
                content_type = upstream.headers.get("Content-Type", "multipart/x-mixed-replace")
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(first_chunk)
                shutil.copyfileobj(upstream, self.wfile, length=4096)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            finally:
                upstream.close()

        def _serve_static(self):
            rel = self.path.lstrip("/") or "index.html"
            file_path = (STATIC_DIR / rel).resolve()
            if STATIC_DIR.resolve() not in file_path.parents and file_path != STATIC_DIR.resolve():
                self.send_error(404)
                return
            if not file_path.is_file():
                self.send_error(404)
                return

            content_types = {
                ".html": "text/html; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
            }
            content_type = content_types.get(file_path.suffix, "application/octet-stream")
            body = file_path.read_bytes()
            self._send_bytes(body, content_type)

    return Handler


def run(cameras_json, known_ids, port):
    handler_cls = build_handler(cameras_json, known_ids)
    httpd = ThreadingHTTPServer(("0.0.0.0", port), handler_cls)
    httpd.daemon_threads = True
    return httpd
