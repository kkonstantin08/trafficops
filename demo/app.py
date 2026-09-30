#!/usr/bin/env python3
"""Small stdlib HTTP service used to demonstrate Kubernetes traffic routing."""

import json
import os
import re
import sys
import threading
import time
import uuid
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


SERVICE = "trafficops-demo"
REGIONS = {"east", "west"}
MARKER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)


class Metrics:
    def __init__(self):
        self.requests = Counter()
        self.observations = Counter()
        self.sums = Counter()
        self.buckets = Counter()
        self.lock = threading.Lock()

    def record(self, version, status, elapsed):
        with self.lock:
            self.requests[(version, status)] += 1
            self.observations[version] += 1
            self.sums[version] += elapsed
            for bound in BUCKETS:
                if elapsed <= bound:
                    self.buckets[(version, bound)] += 1

    def render(self):
        with self.lock:
            lines = [
                "# HELP trafficops_http_requests_total User HTTP requests by version and status.",
                "# TYPE trafficops_http_requests_total counter",
            ]
            for (version, status), count in sorted(self.requests.items()):
                lines.append(
                    f'trafficops_http_requests_total{{version="{version}",status="{status}"}} {count}'
                )
            lines.extend(
                [
                    "# HELP trafficops_http_request_duration_seconds User HTTP request duration.",
                    "# TYPE trafficops_http_request_duration_seconds histogram",
                ]
            )
            for version in sorted(self.observations):
                for bound in BUCKETS:
                    count = self.buckets[(version, bound)]
                    lines.append(
                        f'trafficops_http_request_duration_seconds_bucket{{version="{version}",le="{bound:g}"}} {count}'
                    )
                lines.append(
                    f'trafficops_http_request_duration_seconds_bucket{{version="{version}",le="+Inf"}} {self.observations[version]}'
                )
                lines.append(
                    f'trafficops_http_request_duration_seconds_sum{{version="{version}"}} {self.sums[version]:.9f}'
                )
                lines.append(
                    f'trafficops_http_request_duration_seconds_count{{version="{version}"}} {self.observations[version]}'
                )
            return "\n".join(lines) + "\n"


def marker(query, name, header):
    values = query.get(name, [])
    value = values[0] if values else header
    if value and not MARKER_RE.fullmatch(value):
        raise ValueError(f"invalid {name}")
    return value or uuid.uuid4().hex


def handler_for(version, log_stream=None, force_errors=False):
    if version not in {"v1", "v2"}:
        raise ValueError("APP_VERSION must be v1 or v2")
    metrics = Metrics()
    log_stream = log_stream or sys.stdout

    class Handler(BaseHTTPRequestHandler):
        server_version = "TrafficOps/1"

        def log_message(self, _format, *_args):
            return

        def respond(self, status, body, content_type="application/json; charset=utf-8"):
            payload = body.encode() if isinstance(body, str) else json.dumps(
                body, separators=(",", ":")
            ).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query, keep_blank_values=True)
            started = time.perf_counter()
            request_id = ""
            run_id = ""
            status = 500
            error = None
            try:
                request_id = marker(query, "request_id", self.headers.get("X-Request-ID"))
                run_id = marker(query, "run_id", self.headers.get("X-Run-ID"))
                if parsed.path == "/healthz":
                    status = 200
                    self.respond(status, {"status": "ok", "version": version})
                elif parsed.path == "/metrics":
                    status = 200
                    self.respond(status, metrics.render(), "text/plain; version=0.0.4; charset=utf-8")
                elif parsed.path == "/demo" or parsed.path.startswith("/demo/region/"):
                    region = "default"
                    if parsed.path != "/demo":
                        region = parsed.path.removeprefix("/demo/region/")
                        if region not in REGIONS:
                            status = 404
                            self.respond(status, {"error": "unknown region"})
                            return
                    active_errors = force_errors() if callable(force_errors) else force_errors
                    if active_errors:
                        status = 500
                        self.respond(status, {"service": SERVICE, "error": "controlled demo failure", "version": version})
                    else:
                        status = 200
                        self.respond(
                            status,
                            {
                                "service": SERVICE,
                                "version": version,
                                "region": region,
                                "request_id": request_id,
                                "run_id": run_id,
                            },
                        )
                else:
                    status = 404
                    self.respond(status, {"error": "not found"})
            except ValueError as exc:
                status = 400
                error = str(exc)
                self.respond(status, {"error": error})
            except (BrokenPipeError, ConnectionResetError):
                status = 499
                error = "client disconnected"
            except Exception as exc:
                status = 500
                error = type(exc).__name__
                try:
                    self.respond(status, {"error": "internal server error"})
                except (BrokenPipeError, ConnectionResetError):
                    pass
            finally:
                elapsed = time.perf_counter() - started
                is_user_request = parsed.path not in {"/healthz", "/metrics"}
                if is_user_request:
                    metrics.record(version, status, elapsed)
                record = {
                    "event": "access",
                    "service": SERVICE,
                    "version": version,
                    "path": parsed.path,
                    "status": status,
                    "duration_seconds": round(elapsed, 6),
                    "request_id": request_id,
                    "run_id": run_id,
                }
                log_stream.write(json.dumps(record, separators=(",", ":")) + "\n")
                log_stream.flush()
                if status >= 500:
                    record["event"] = "error"
                    record["error"] = error or "controlled demo failure"
                    log_stream.write(json.dumps(record, separators=(",", ":")) + "\n")
                    log_stream.flush()

    return Handler


def main():
    version = os.environ.get("APP_VERSION", "v1")
    def force_errors():
        try:
            return open("/etc/trafficops/APP_FORCE_ERRORS", encoding="utf-8").read().strip().lower() == "true"
        except OSError:
            return os.environ.get("APP_FORCE_ERRORS", "false").lower() == "true"
    server = ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), handler_for(version, force_errors=force_errors))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
