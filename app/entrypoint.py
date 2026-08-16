import logging
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from cameras_config import ConfigError, load_cameras, render_go2rtc_streams_yaml, to_public_json
from server import GO2RTC_API, StreamUnavailable, mark_stream_result, open_camera_stream
from server import run as run_server

logging.basicConfig(level=logging.INFO, format="[camfeeder] %(message)s")
log = logging.getLogger("entrypoint")

BASE_CONFIG = "/app/go2rtc/base.yaml"
STREAMS_CONFIG = "/run/go2rtc.streams.yaml"
CAMERAS_CONFIG = "/config/cameras.yml"
DASHBOARD_PORT = 200


def _wait_for_go2rtc(timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"{GO2RTC_API}/api/streams", timeout=1).close()
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    return False


def _test_camera(cam):
    try:
        upstream, _ = open_camera_stream(cam.id, timeout=20)
    except StreamUnavailable as e:
        mark_stream_result(cam.id, ok=False, detail=str(e))
        log.warning("startup test: camera %s (%s) - FAILED: %s", cam.id, cam.name, e)
        return
    upstream.close()
    mark_stream_result(cam.id, ok=True)
    log.info("startup test: camera %s (%s) - OK", cam.id, cam.name)


def test_all_cameras(cameras):
    enabled = [c for c in cameras if c.enabled]
    if not enabled:
        return
    if not _wait_for_go2rtc():
        log.warning("startup test: go2rtc API never became reachable, skipping")
        return
    log.info("startup test: checking RTSP connectivity for %d camera(s)...", len(enabled))
    with ThreadPoolExecutor(max_workers=min(5, len(enabled))) as pool:
        list(pool.map(_test_camera, enabled))
    log.info("startup test: done")


def main():
    cameras_config = CAMERAS_CONFIG
    dashboard_port = DASHBOARD_PORT

    try:
        cameras = load_cameras(cameras_config)
    except ConfigError as e:
        log.error("cameras.yml problem: %s", e)
        sys.exit(1)

    log.info("loaded %d camera(s) from %s", len(cameras), cameras_config)

    with open(STREAMS_CONFIG, "w", encoding="utf-8") as f:
        f.write(render_go2rtc_streams_yaml(cameras))

    go2rtc = subprocess.Popen(
        ["go2rtc", "-c", BASE_CONFIG, "-c", STREAMS_CONFIG],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    log.info("go2rtc started (pid %d)", go2rtc.pid)

    stopping = threading.Event()
    httpd_holder = {}

    def shutdown(*_):
        if stopping.is_set():
            return
        stopping.set()
        log.info("shutting down")
        go2rtc.terminate()
        try:
            go2rtc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            go2rtc.kill()
        httpd = httpd_holder.get("httpd")
        if httpd:
            threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    def watchdog():
        code = go2rtc.wait()
        if not stopping.is_set():
            log.error("go2rtc exited unexpectedly (code %s); exiting container", code)
            os._exit(1)

    threading.Thread(target=watchdog, daemon=True).start()
    threading.Thread(target=test_all_cameras, args=(cameras,), daemon=True).start()

    known_ids = {c.id for c in cameras if c.enabled}
    cameras_json = to_public_json(cameras)
    httpd = run_server(cameras_json, known_ids, dashboard_port)
    httpd_holder["httpd"] = httpd

    log.info("dashboard listening on :%d", dashboard_port)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
