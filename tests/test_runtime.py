import tempfile
import threading
import time
import unittest

from controller.runtime import ControlPlane
from controller.store import Store


class FakeKube:
    def __init__(self):
        self.weights_value = {"v1": 90, "v2": 10}
        self.changes = []
        self.fail_confirmation = False

    def set_weights(self, v1, v2):
        self.changes.append((v1, v2))
        self.weights_value = {"v1": v1, "v2": v2}

    def wait_route(self, v1, v2):
        if self.fail_confirmation:
            raise RuntimeError("Gateway did not confirm route")
        return {"v1": v1, "v2": v2}

    def weights(self):
        return self.weights_value

    def deployments(self):
        return []


class FakeProm:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def canary_snapshot(self, _window):
        return self.snapshot

    def metrics(self):
        raise RuntimeError("Prometheus unavailable")


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name + "/state.sqlite3")
        self.kube = FakeKube()
        now = time.time()
        self.prom = FakeProm({"requests": 100, "errors": 6, "sample_time": now, "target_up": 1})
        self.plane = ControlPlane(self.store, self.kube, self.prom)
        self.store.set_state("release", {"status": "canary", "weights": {"v1": 90, "v2": 10},
                                           "started_at": now - 61, "breaches": 0})

    def tearDown(self):
        self.temp.cleanup()

    def test_first_threshold_breach_blocks_weight_change(self):
        with self.assertRaisesRegex(RuntimeError, "blocked"):
            self.plane.set_weight(20)
        self.assertEqual(self.kube.changes, [])
        self.assertEqual(self.store.get_state("release")["last_decision"]["error_ratio"], 0.06)

    def test_manual_rollback_does_not_query_prometheus(self):
        self.plane.probe_version = lambda version: self.assertEqual(version, "v1")
        result = self.plane.rollback()
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(self.kube.changes, [(100, 0)])
        self.assertEqual(self.store.get_state("release")["status"], "rolled-back")

    def test_unconfirmed_route_change_requires_reconciliation(self):
        self.kube.weights_value = {"v1": 100, "v2": 0}
        self.store.set_state("release", {"status": "stable", "weights": {"v1": 100, "v2": 0}})
        self.kube.fail_confirmation = True
        with self.assertRaisesRegex(RuntimeError, "confirm"):
            self.plane.start_release()
        state = self.store.get_state("release")
        self.assertEqual(state["status"], "reconcile-required")
        self.assertTrue(state["reconcile_required"])
        self.assertEqual(state["actual_weights"], {"v1": 90, "v2": 10})

    def test_reconcile_clears_resolved_route_flag_but_keeps_failed_rollback_blocked(self):
        self.kube.weights_value = {"v1": 100, "v2": 0}
        self.store.set_state("release", {"status": "reconcile-required", "weights": {"v1": 100, "v2": 0}})
        self.plane.reconcile()
        state = self.store.get_state("release")
        self.assertEqual(state["status"], "stable")
        self.assertFalse(state["reconcile_required"])

        self.store.set_state("release", {"status": "rollback-failed", "weights": {"v1": 100, "v2": 0},
                                           "reconcile_required": True})
        self.plane.reconcile()
        state = self.store.get_state("release")
        self.assertEqual(state["status"], "rollback-failed")
        self.assertTrue(state["reconcile_required"])

    def test_failed_automatic_rollback_is_visible_and_not_retried(self):
        self.kube.fail_confirmation = True
        state = self.store.get_state("release")
        state["breaches"] = 1
        self.store.set_state("release", state)
        self.plane.probe_version = lambda _version: None
        self.plane._monitor_once()
        result = self.store.get_state("release")
        self.assertEqual(result["status"], "rollback-failed")
        self.assertTrue(result["reconcile_required"])
        changes = list(self.kube.changes)
        self.plane._monitor_once()
        self.assertEqual(self.kube.changes, changes)

    def test_traffic_never_submits_after_duration_or_above_ten_in_flight(self):
        lock = threading.Lock()
        state = {"active": 0, "maximum": 0, "started": None, "late": False}

        def slow_send(_url, _headers):
            with lock:
                state["started"] = state["started"] or time.monotonic()
                state["active"] += 1
                state["maximum"] = max(state["maximum"], state["active"])
                if time.monotonic() > state["started"] + 1.1:
                    state["late"] = True
            time.sleep(1.3)
            with lock:
                state["active"] -= 1
            return True

        self.plane.traffic_sender = slow_send
        self.plane.start_traffic(rate=20, duration=1, path="/demo")
        self.plane.traffic_thread.join(timeout=4)
        self.assertFalse(self.plane.traffic_thread.is_alive())
        self.assertEqual(self.store.get_state("traffic")["sent"], 10)
        self.assertLessEqual(state["maximum"], 10)
        self.assertFalse(state["late"])

    def test_traffic_progress_is_persisted_during_slow_rate_series(self):
        self.plane.traffic_sender = lambda _url, _headers: (time.sleep(0.05) or True)
        self.plane.start_traffic(rate=1, duration=4, path="/demo")
        time.sleep(1.2)
        state = self.store.get_state("traffic")
        self.assertEqual(state["status"], "running")
        self.assertGreaterEqual(state["sent"], 1)
        self.plane.stop_traffic()


if __name__ == "__main__":
    unittest.main()
