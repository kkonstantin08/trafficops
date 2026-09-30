#!/usr/bin/env python3
"""Run the bounded TrafficOps release and rollback scenario against the local VM."""

import argparse
import http.cookiejar
import ipaddress
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

EXPECTED_POLICY = {
    "window_seconds": 60,
    "min_requests": 30,
    "error_threshold": 0.05,
    "required_breaches": 2,
    "check_seconds": 10,
    "max_sample_age_seconds": 30,
}
TRAFFIC = {"rate": 20, "duration": 180, "path": "/demo"}
PROJECTION_GRACE = 130


class ScenarioError(RuntimeError):
    pass


class TrafficOps:
    def __init__(self, origin):
        self.origin = origin.rstrip("/")
        self.csrf = None
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def request(self, method, path, payload=None, timeout=None, gateway_host=False):
        body = None if payload is None else json.dumps(payload).encode()
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if method == "POST":
            headers["Origin"] = self.origin
            if self.csrf:
                headers["X-CSRF-Token"] = self.csrf
        if gateway_host:
            headers["Host"] = "trafficops.local"
        request = urllib.request.Request(self.origin + path, data=body, method=method, headers=headers)
        try:
            with self.opener.open(request, timeout=timeout or (45 if method == "POST" else 25)) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read()
            exc.close()
            return exc.code, body
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            raise ScenarioError(f"{method} {path} did not complete: {type(exc).__name__}") from exc

    def get(self, path):
        status, body = self.request("GET", path)
        if status != 200:
            raise ScenarioError(f"GET {path} returned HTTP {status}")
        try:
            return json.loads(body)
        except (ValueError, TypeError) as exc:
            raise ScenarioError(f"GET {path} returned invalid JSON") from exc

    def post(self, path, payload=None):
        status, body = self.request("POST", path, payload)
        if status != 200:
            raise ScenarioError(f"POST {path} returned HTTP {status}")
        try:
            return json.loads(body)
        except (ValueError, TypeError) as exc:
            raise ScenarioError(f"POST {path} returned invalid JSON") from exc

    def login(self, password):
        status, body = self.request("POST", "/api/login", {"password": password}, timeout=15)
        if status != 200:
            raise ScenarioError(f"controller login returned HTTP {status}")
        try:
            payload = json.loads(body)
            self.csrf = payload["csrf"]
        except (ValueError, TypeError, KeyError) as exc:
            raise ScenarioError("controller login response was invalid") from exc

    def probe(self, expected_version):
        status, body = self.request("GET", "/demo", timeout=10, gateway_host=True)
        if status != 200:
            raise ScenarioError(f"Gateway demo probe returned HTTP {status}")
        try:
            payload = json.loads(body)
        except (ValueError, TypeError) as exc:
            raise ScenarioError("Gateway demo probe returned invalid JSON") from exc
        if payload.get("service") != "trafficops-demo" or payload.get("version") != expected_version:
            raise ScenarioError(f"Gateway returned an unexpected version (expected {expected_version})")
        return payload


def node_origin():
    kubeconfig = os.environ.get("KUBECONFIG") or str(Path.home() / ".kube" / "trafficops.conf")
    env = os.environ.copy()
    env["KUBECONFIG"] = kubeconfig
    try:
        result = subprocess.run(
            ["kubectl", "--request-timeout=10s", "get", "nodes", "-o",
             "jsonpath={.items[0].status.addresses[?(@.type==\"InternalIP\")].address}"],
            check=True, capture_output=True, text=True, timeout=15, env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ScenarioError("cannot read the Kubernetes node InternalIP from the TrafficOps kubeconfig") from exc
    address = result.stdout.strip()
    try:
        ip = ipaddress.ip_address(address)
    except ValueError as exc:
        raise ScenarioError("Kubernetes returned an invalid node IP") from exc
    if not (ip.is_private or ip.is_loopback or ip.is_link_local):
        raise ScenarioError("refusing to send the controller password to a non-local node address")
    host = f"[{address}]" if ip.version == 6 else address
    return f"http://{host}:30080"


def check_policy(policy):
    if not isinstance(policy, dict):
        raise ScenarioError("controller did not return its canary policy")
    for key, expected in EXPECTED_POLICY.items():
        actual = policy.get(key)
        if isinstance(expected, float):
            valid = isinstance(actual, (int, float)) and abs(float(actual) - expected) < 1e-9
        else:
            valid = actual == expected
        if not valid:
            raise ScenarioError("verify-scenario requires the documented default canary policy")


def fresh_safe_decision(release, now):
    decision = release.get("last_decision") or {}
    try:
        sample_time = float(decision["sample_time"])
        requests = int(decision["requests"])
        ratio = float(decision["error_ratio"])
        started_at = float(release["started_at"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    if not all(math.isfinite(value) for value in (sample_time, ratio, started_at, now)):
        return False
    return (release.get("status") == "canary" and decision.get("state") == "observe"
            and decision.get("target_up") is True and requests >= EXPECTED_POLICY["min_requests"]
            and ratio <= EXPECTED_POLICY["error_threshold"]
            and now >= started_at + EXPECTED_POLICY["window_seconds"]
            and sample_time >= started_at and -5 <= now - sample_time <= EXPECTED_POLICY["max_sample_age_seconds"])


def wait_for_healthy(client):
    timeout = (EXPECTED_POLICY["window_seconds"] + EXPECTED_POLICY["max_sample_age_seconds"]
               + 3 * EXPECTED_POLICY["check_seconds"] + 15)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        overview = client.get("/api/overview")
        release = overview.get("release", {})
        if release.get("status") in {"rolled-back", "rollback-failed", "reconcile-required"}:
            raise ScenarioError("healthy canary did not remain active; see the release state and journal")
        if fresh_safe_decision(release, time.time()):
            print("Healthy canary has a complete fresh window with at least 30 v2 requests.")
            return release
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    raise ScenarioError(f"healthy canary was not confirmed within {timeout} seconds")


def wait_for_auto_rollback(client):
    timeout = (PROJECTION_GRACE + EXPECTED_POLICY["window_seconds"]
               + (EXPECTED_POLICY["required_breaches"] + 2) * EXPECTED_POLICY["check_seconds"]
               + EXPECTED_POLICY["max_sample_age_seconds"] + 30)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        overview = client.get("/api/overview")
        release = overview.get("release", {})
        status = release.get("status")
        decision = release.get("last_decision") or {}
        if status == "rolled-back" and str(release.get("reason", "")).startswith("automatic rollback"):
            try:
                ratio, requests = float(decision["error_ratio"]), int(decision["requests"])
                age = time.time() - float(decision["sample_time"])
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ScenarioError("automatic rollback is missing its source metrics") from exc
            if (decision.get("state") != "rollback" or ratio <= EXPECTED_POLICY["error_threshold"]
                    or requests < EXPECTED_POLICY["min_requests"] or not -5 <= age <= EXPECTED_POLICY["max_sample_age_seconds"]):
                raise ScenarioError("automatic rollback metrics are not a fresh threshold breach")
            return release
        if status in {"rollback-failed", "reconcile-required"}:
            raise ScenarioError("automatic rollback failed; inspect the reason and actual route weights")
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    raise ScenarioError(f"automatic rollback was not confirmed within {timeout} seconds")


def cleanup(client):
    """Attempt every restore action and return all errors without masking the scenario failure."""
    errors = []
    actions = [
        ("stop traffic", "/api/traffic/stop", None),
        ("disable v2 errors", "/api/incident/errors", {"enabled": False}),
        ("manual rollback", "/api/release/rollback", None),
        ("logout", "/api/logout", {}),
    ]
    for label, path, payload in actions:
        try:
            client.post(path, payload)
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    return errors


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    password_file = Path(config_home) / "trafficops" / "admin-password"
    try:
        password = password_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ScenarioError(f"controller password file is unavailable: {password_file}") from exc
    if not password:
        raise ScenarioError("controller password file is empty")

    client = TrafficOps(node_origin())
    if client.get("/healthz").get("status") != "ok":
        raise ScenarioError("controller health endpoint is not ready")
    client.login(password)
    del password

    mutated = False
    primary_error = None
    cleanup_errors = []
    try:
        overview = client.get("/api/overview")
        check_policy(overview.get("policy"))
        release = overview.get("release", {})
        services = overview.get("services", {})
        if release.get("reconcile_required") or release.get("status") not in {"stable", "rolled-back"}:
            raise ScenarioError("start from a stable or rolled-back release with no reconciliation required")
        if services.get("weights") != {"v1": 100, "v2": 0}:
            raise ScenarioError("start with demo-route weights v1=100 and v2=0")
        if (overview.get("traffic") or {}).get("status") == "running":
            raise ScenarioError("a traffic series is already running")

        print("Resetting demo-v2 error switch; waiting 130 seconds for ConfigMap projection.")
        mutated = True
        client.post("/api/incident/errors", {"enabled": False})
        time.sleep(PROJECTION_GRACE)

        print("Running healthy canary with 20 requests/s for at most 180 seconds.")
        client.post("/api/traffic/start", TRAFFIC)
        client.post("/api/release/start")
        wait_for_healthy(client)
        client.post("/api/release/complete")
        client.probe("v2")
        print("Healthy release completed and HTTP v2 was confirmed through Gateway.")
        client.post("/api/release/rollback")
        client.probe("v1")
        client.post("/api/traffic/stop")
        print("Manual rollback confirmed HTTP v1 through Gateway.")

        print("Enabling controlled v2 errors and running a failed canary.")
        client.post("/api/incident/errors", {"enabled": True})
        client.post("/api/traffic/start", TRAFFIC)
        client.post("/api/release/start")
        failed_release = wait_for_auto_rollback(client)
        client.probe("v1")
        operations = client.get("/api/operations").get("operations", [])
        if not any(op.get("kind") == "release-rollback" and op.get("status") == "succeeded"
                   and str(op.get("reason", "")).startswith("automatic rollback") for op in operations):
            raise ScenarioError("journal does not contain the confirmed automatic rollback")
        print("Failed canary automatically rolled back; its fresh 5xx decision and HTTP v1 were confirmed.")
    except Exception as exc:
        primary_error = exc
    finally:
        if mutated:
            cleanup_errors = cleanup(client)
        else:
            try:
                client.post("/api/logout", {})
            except Exception as exc:
                cleanup_errors = [f"logout: {exc}"]

    if primary_error:
        print(f"ERROR: {primary_error}", file=sys.stderr)
    for error in cleanup_errors:
        print(f"CLEANUP ERROR: {error}", file=sys.stderr)
    if primary_error or cleanup_errors:
        return 1
    print("Scenario passed; finally stopped traffic, disabled v2 errors, manually rolled back, and logged out.")
    return 0


def main():
    try:
        return run()
    except ScenarioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("ERROR: interrupted; cleanup was attempted after mutations began", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
