from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import random
import time
from urllib.parse import parse_qs, urlparse

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

ENVIRONMENT = os.getenv("ENVIRONMENT", "k3s")
SERVICE = os.getenv("SERVICE_NAME", "demo-api")
PORT = int(os.getenv("PORT", "8080"))

REQUESTS = Counter(
    "demo_http_requests_total",
    "Demo application HTTP requests.",
    ["environment", "service", "method", "path", "status"],
)
DURATION = Histogram(
    "demo_http_request_duration_seconds",
    "Demo application request duration.",
    ["environment", "service", "method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
IN_PROGRESS = Gauge(
    "demo_http_requests_in_progress",
    "Demo application requests currently in progress.",
    ["environment", "service"],
)


class Handler(BaseHTTPRequestHandler):
    server_version = "cloud-ops-demo/0.1"

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/metrics":
            body = generate_latest()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/healthz":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path not in ("/", "/work"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        query = parse_qs(parsed.query)
        latency_ms = min(max(float(query.get("latency_ms", [random.uniform(10, 60)])[0]), 0), 5000)
        fail = query.get("fail", ["false"])[0].lower() in {"1", "true", "yes"}
        status = HTTPStatus.INTERNAL_SERVER_ERROR if fail else HTTPStatus.OK
        labels = (ENVIRONMENT, SERVICE, "GET", parsed.path)
        started = time.monotonic()
        IN_PROGRESS.labels(ENVIRONMENT, SERVICE).inc()
        try:
            time.sleep(latency_ms / 1000)
            self._send_json(status, {"status": "error" if fail else "ok", "latency_ms": latency_ms})
        finally:
            IN_PROGRESS.labels(ENVIRONMENT, SERVICE).dec()
            DURATION.labels(*labels).observe(time.monotonic() - started)
            REQUESTS.labels(*labels, str(status.value)).inc()

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}", flush=True)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"demo-app listening on :{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

