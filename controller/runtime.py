import json
import os
import re
import threading
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from controller.clients import ClusterError, Kubernetes, Prometheus
from controller.rollback import evaluate_canary
from controller.store import Store

REGION_PATHS = {"/demo", "/demo/region/east", "/demo/region/west"}
MARKER = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
POLICY = {
    "window_seconds": int(os.getenv("CANARY_WINDOW_SECONDS", "60")),
    "min_requests": int(os.getenv("CANARY_MIN_REQUESTS", "30")),
    "error_threshold": float(os.getenv("CANARY_ERROR_THRESHOLD", "0.05")),
    "required_breaches": int(os.getenv("CANARY_REQUIRED_BREACHES", "2")),
    "check_seconds": int(os.getenv("CANARY_CHECK_SECONDS", "10")),
    "max_sample_age_seconds": int(os.getenv("CANARY_MAX_SAMPLE_AGE_SECONDS", "30")),
}


class ControlPlane:
    def __init__(self, store=None, kube=None, prom=None, gateway=None, logs=None, traffic_sender=None):
        self.store = store or Store(os.getenv("TRAFFICOPS_DB", "/var/lib/trafficops/controller.sqlite3"))
        self.kube = kube or Kubernetes()
        self.prom = prom or Prometheus()
        self.gateway = gateway or os.getenv("TRAFFICOPS_GATEWAY", "http://127.0.0.1:30080")
        self.logs_dir = Path(logs or "/var/lib/trafficops/fluentd/logs")
        self.operation_lock = threading.Lock()
        self.traffic_lock = threading.Lock()
        self.traffic_stop = threading.Event()
        self.traffic_thread = None
        self.traffic_sender = traffic_sender
        self.monitor_stop = threading.Event()

    def start(self):
        self.reconcile()
        threading.Thread(target=self.monitor, name="canary-monitor", daemon=True).start()

    def stop(self):
        self.monitor_stop.set()
        self.stop_traffic()

    def reconcile(self):
        self.store.interrupt_running("controller restarted during operation")
        traffic = self.store.get_state("traffic", {})
        if traffic.get("status") == "running":
            traffic["status"] = "interrupted"
            self.store.set_state("traffic", traffic)
        state = self.store.get_state("release", {"status": "stable", "weights": {"v1": 100, "v2": 0}})
        try:
            actual = self.kube.weights()
            if actual != state.get("weights", {"v1": 100, "v2": 0}):
                state.update(status="reconcile-required", reconcile_required=True, actual_weights=actual)
            elif state.get("status") == "rollback-failed":
                state.update(reconcile_required=True, actual_weights=actual)
            else:
                if state.get("status") == "reconcile-required":
                    state["status"] = "canary" if "started_at" in state else "stable"
                state["reconcile_required"] = False
                state.pop("actual_weights", None)
            self.store.set_state("release", state)
        except Exception as exc:
            state.update(status="reconcile-required", reconcile_required=True, error=str(exc))
            self.store.set_state("release", state)

    def overview(self):
        state = self.store.get_state("release", {"status": "stable", "weights": {"v1": 100, "v2": 0}})
        try:
            services = {"status": "available", "updated_at": time.time(), "deployments": self.kube.deployments(),
                        "weights": self.kube.weights()}
        except Exception as exc:
            services = {"status": "unavailable", "updated_at": None, "error": str(exc), "deployments": [], "weights": None}
        return {"updated_at": time.time(), "release": state, "services": services,
                "metrics": self.prom.metrics(), "traffic": self.store.get_state("traffic", {"status": "idle"}),
                "policy": POLICY}

    def logs(self, marker, limit):
        if marker and not MARKER.fullmatch(marker):
            raise ValueError("invalid marker")
        if not self.logs_dir.is_dir():
            return {"status": "unavailable", "updated_at": None, "entries": [],
                    "error": "Fluentd log destination is unavailable"}
        entries = []
        try:
            files = sorted(self.logs_dir.glob("trafficops.*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            return {"status": "unavailable", "updated_at": None, "entries": [],
                    "error": "Fluentd log destination could not be read"}
        for path in files:
            if path.is_symlink() or not path.resolve().is_relative_to(self.logs_dir.resolve()):
                continue
            try:
                with path.open(encoding="utf-8", errors="replace") as stream:
                    for line in deque(stream, maxlen=5000):
                        try:
                            record = json.loads(line)
                        except ValueError:
                            continue
                        if record.get("event") not in {"access", "error"}:
                            continue
                        if marker and marker not in (record.get("request_id"), record.get("run_id")):
                            continue
                        entries.append(record)
            except OSError:
                continue
            if len(entries) >= limit:
                break
        entries.sort(key=lambda row: row.get("cri_time", ""), reverse=True)
        latest_time = None
        if entries and entries[0].get("cri_time"):
            try:
                latest_time = datetime.fromisoformat(entries[0]["cri_time"].replace("Z", "+00:00")).timestamp()
            except ValueError:
                pass
        return {"status": "available", "updated_at": latest_time, "entries": entries[:limit]}

    def release_change(self, kind, action, details=None, reason=None):
        if not self.operation_lock.acquire(blocking=False):
            raise RuntimeError("another control operation is running")
        op_id = self.store.operation(kind, "running", reason, details)
        try:
            self.store.update_operation(op_id, "running", details={"intent": "persisted"})
            result = action()
            self.store.update_operation(op_id, "succeeded", details=result if isinstance(result, dict) else {"result": result})
            return {"operation_id": op_id, "status": "succeeded", **(result if isinstance(result, dict) else {})}
        except Exception as exc:
            self.store.update_operation(op_id, "failed", str(exc))
            if kind in {"release-start", "release-weight", "release-complete", "release-rollback"}:
                try:
                    actual = self.kube.weights()
                    state = self.store.get_state("release", {})
                    if actual != state.get("weights", {"v1": 100, "v2": 0}):
                        state.update(status="reconcile-required", reconcile_required=True, actual_weights=actual,
                                     error=f"{kind} failed: {exc}")
                        self.store.set_state("release", state)
                except Exception:
                    state = self.store.get_state("release", {})
                    state.update(status="reconcile-required", reconcile_required=True,
                                 error=f"{kind} failed and actual route weights are unavailable: {exc}")
                    self.store.set_state("release", state)
            raise
        finally:
            self.operation_lock.release()

    def start_release(self):
        def action():
            state = self.store.get_state("release", {"status": "stable", "weights": {"v1": 100, "v2": 0}})
            if state.get("reconcile_required") or state.get("status") == "reconcile-required":
                raise RuntimeError("route reconciliation is required before another release")
            if state.get("status") in {"canary", "completed"}:
                raise RuntimeError("an active release already exists")
            self.kube.set_weights(90, 10)
            weights = self.kube.wait_route(90, 10)
            state = {"status": "canary", "started_at": time.time(), "weights": weights, "breaches": 0,
                     "last_decision": {"state": "unknown", "reason": "waiting for a complete fresh window"}}
            self.store.set_state("release", state)
            return {"weights": weights, "started_at": state["started_at"]}
        return self.release_change("release-start", action, {"weights": {"v1": 90, "v2": 10}})

    def latest_decision(self, state):
        snapshot = self.prom.canary_snapshot(POLICY["window_seconds"])
        decision = evaluate_canary(snapshot, POLICY, state.get("breaches", 0), state.get("started_at", time.time()), time.time())
        return snapshot, decision

    def set_weight(self, percent):
        def action():
            state = self.store.get_state("release", {})
            if state.get("status") != "canary" or state.get("reconcile_required"):
                raise RuntimeError("no active canary release")
            snapshot, decision = self.latest_decision(state)
            state["last_decision"] = decision
            self.store.set_state("release", state)
            if decision["state"] != "observe" or decision.get("error_ratio", 0) > POLICY["error_threshold"]:
                raise RuntimeError("canary weight change is blocked until fresh metrics are safe")
            self.kube.set_weights(100 - percent, percent)
            weights = self.kube.wait_route(100 - percent, percent)
            state.update(weights=weights, breaches=decision["breaches"])
            self.store.set_state("release", state)
            return {"weights": weights, "metrics": {**snapshot, **decision}}
        return self.release_change("release-weight", action, {"percent": percent})

    def complete_release(self):
        def action():
            state = self.store.get_state("release", {})
            if state.get("status") != "canary" or state.get("reconcile_required"):
                raise RuntimeError("no active canary release")
            snapshot, decision = self.latest_decision(state)
            state["last_decision"] = decision
            self.store.set_state("release", state)
            if decision["state"] != "observe" or decision.get("error_ratio", 0) > POLICY["error_threshold"]:
                raise RuntimeError("release completion requires a complete fresh window below the error threshold")
            self.kube.set_weights(0, 100)
            weights = self.kube.wait_route(0, 100)
            self.probe_version("v2")
            state.update(status="completed", weights=weights, breaches=decision["breaches"], completed_at=time.time())
            self.store.set_state("release", state)
            return {"weights": weights, "metrics": {**snapshot, **decision}}
        return self.release_change("release-complete", action)

    def rollback(self, reason="manual rollback"):
        def action():
            self.kube.set_weights(100, 0)
            weights = self.kube.wait_route(100, 0)
            self.probe_version("v1")
            state = {"status": "rolled-back", "weights": weights, "reason": reason, "rolled_back_at": time.time(),
                     "reconcile_required": False}
            self.store.set_state("release", state)
            return {"weights": weights, "confirmed_version": "v1", "reason": reason}
        return self.release_change("release-rollback", action, {"route": {"v1": 100, "v2": 0}}, reason)

    def probe_version(self, version):
        request = urllib.request.Request(self.gateway + "/demo", headers={"Host": "trafficops.local"})
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read())
        if payload.get("version") != version:
            raise ClusterError(f"Gateway returned {payload.get('version')}, expected {version}")

    def probe_demo(self):
        request = urllib.request.Request(self.gateway + "/demo", headers={"Host": "trafficops.local"})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read())
            finally:
                exc.close()
        if payload.get("service") != "trafficops-demo" or payload.get("version") not in {"v1", "v2"}:
            raise ClusterError("Gateway demo probe returned an invalid application response")
        return {"version": payload["version"], "http_status": 500 if "error" in payload else 200}

    def monitor(self):
        while not self.monitor_stop.wait(POLICY["check_seconds"]):
            if not self.operation_lock.acquire(blocking=False):
                continue
            try:
                self._monitor_once()
            finally:
                self.operation_lock.release()

    def _monitor_once(self):
        state = self.store.get_state("release", {})
        if state.get("status") != "canary" or state.get("reconcile_required"):
            return
        try:
            snapshot, decision = self.latest_decision(state)
        except Exception as exc:
            snapshot, decision = {}, {"state": "unknown", "breaches": 0, "reason": str(exc)}
        state["breaches"] = decision.get("breaches", 0) if decision["state"] != "unknown" else 0
        state["last_decision"] = decision
        self.store.set_state("release", state)
        op_id = self.store.operation("canary-check", "succeeded", decision["reason"],
                                     {"metrics": {**snapshot, **decision}, "checked_at": time.time()})
        if decision["state"] == "rollback":
            rollback_id = self.store.operation("release-rollback", "running", "automatic rollback: " + decision["reason"],
                                               {"metrics": {**snapshot, **decision}})
            try:
                self.kube.set_weights(100, 0)
                weights = self.kube.wait_route(100, 0)
                self.probe_version("v1")
                self.store.set_state("release", {"status": "rolled-back", "weights": weights,
                                     "reason": "automatic rollback: " + decision["reason"],
                                     "rolled_back_at": time.time(), "reconcile_required": False,
                                     "last_decision": decision})
                self.store.update_operation(rollback_id, "succeeded", details={"confirmed_version": "v1"})
                self.store.update_operation(op_id, "succeeded", details={"rollback_confirmed": True})
            except Exception as exc:
                self.store.update_operation(rollback_id, "failed", str(exc), {"rollback_confirmed": False})
                self.store.update_operation(op_id, "failed", "automatic rollback failed: " + str(exc), {"rollback_confirmed": False})
                try:
                    actual = self.kube.weights()
                except Exception:
                    actual = None
                self.store.set_state("release", {"status": "rollback-failed", "weights": actual,
                                     "actual_weights": actual, "reason": "automatic rollback failed: " + str(exc),
                                     "last_decision": decision, "reconcile_required": True,
                                     "failed_at": time.time()})

    def set_errors(self, enabled):
        def action():
            self.kube.set_errors(enabled)
            return {"enabled": enabled, "note": "v2 receives the ConfigMap through the fixed pod mount"}
        return self.release_change("incident-errors", action, {"enabled": enabled})

    def restart_pod(self):
        def action():
            name = self.kube.restart_one_pod()
            self.kube.wait_pod_replacement(name)
            return {"pod": name, "deleted": True, "replacement_running": True, "replacement_ready": True,
                    "gateway_probe": self.probe_demo()}
        return self.release_change("incident-restart-pod", action)

    def start_traffic(self, rate=10, duration=180, path="/demo"):
        count = rate * duration
        if not 1 <= rate <= 20 or not 1 <= duration <= 180 or count > 3600 or path not in REGION_PATHS:
            raise ValueError("invalid bounded demo traffic request")
        with self.traffic_lock:
            if self.traffic_thread and self.traffic_thread.is_alive():
                raise RuntimeError("traffic generator is already running")
            self.traffic_stop.clear()
            state = {"status": "running", "run_id": "run-" + uuid.uuid4().hex[:16], "rate": rate,
                     "duration": duration, "path": path, "sent": 0, "failed": 0, "started_at": time.time()}
            self.store.set_state("traffic", state)
            op_id = self.store.operation("traffic-start", "running", details=state)
            self.traffic_thread = threading.Thread(target=self._traffic, args=(state, op_id), daemon=True)
            self.traffic_thread.start()
            return {"operation_id": op_id, **state}

    def _traffic(self, state, op_id):
        total, interval = state["rate"] * state["duration"], 1 / state["rate"]
        started = time.monotonic()
        pending = set()
        last_saved = started

        def send(index):
            url = self.gateway + state["path"]
            headers = {"Host": "trafficops.local", "X-Request-ID": f"{state['run_id']}-{index}",
                       "X-Run-ID": state["run_id"]}
            if self.traffic_sender:
                return self.traffic_sender(url, headers)
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=4) as response:
                    response.read()
                return True
            except (OSError, urllib.error.URLError, TimeoutError):
                return False

        def collect(done):
            nonlocal last_saved
            for future in done:
                pending.remove(future)
                if not future.result():
                    state["failed"] += 1
            if time.monotonic() - last_saved >= 1:
                self.store.set_state("traffic", state)
                last_saved = time.monotonic()

        def save_progress():
            nonlocal last_saved
            if time.monotonic() - last_saved >= 1:
                self.store.set_state("traffic", state)
                last_saved = time.monotonic()

        with ThreadPoolExecutor(max_workers=10, thread_name_prefix="trafficops-traffic") as pool:
            for index in range(total):
                if self.traffic_stop.is_set() or time.monotonic() >= started + state["duration"]:
                    break
                deadline = started + index * interval
                done, _ = wait(pending, return_when=FIRST_COMPLETED, timeout=0) if pending else (set(), set())
                collect(done)
                save_progress()
                while not self.traffic_stop.is_set() and len(pending) >= 10:
                    done, _ = wait(pending, return_when=FIRST_COMPLETED, timeout=0.1)
                    collect(done)
                    save_progress()
                    if time.monotonic() >= started + state["duration"]:
                        break
                if time.monotonic() >= started + state["duration"]:
                    break
                delay = deadline - time.monotonic()
                if delay > 0 and self.traffic_stop.wait(delay):
                    break
                if self.traffic_stop.is_set() or time.monotonic() >= started + state["duration"]:
                    break
                pending.add(pool.submit(send, index))
                state["sent"] += 1
                save_progress()
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED, timeout=0.1)
                collect(done)
                self.store.set_state("traffic", state)
        state["status"] = "stopped" if self.traffic_stop.is_set() else "completed"
        state["finished_at"] = time.time()
        self.store.set_state("traffic", state)
        self.store.update_operation(op_id, "succeeded", details=state)

    def stop_traffic(self):
        self.traffic_stop.set()
        if self.traffic_thread and self.traffic_thread.is_alive():
            self.traffic_thread.join(timeout=6)
        return self.store.get_state("traffic", {"status": "idle"})
