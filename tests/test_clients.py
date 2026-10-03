import re
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from controller.clients import ClusterError, Kubernetes


class RouteGenerationTests(unittest.TestCase):
    def test_controller_route_allows_bounded_pod_recovery(self):
        route = (Path(__file__).resolve().parents[1] / "deploy/controller-route.yaml").read_text()
        self.assertIn("request: 100s", route)
        self.assertIn("backendRequest: 100s", route)

    def test_controller_and_gateway_idle_timeouts_avoid_server_first_close(self):
        root = Path(__file__).resolve().parents[1]
        controller = (root / "deploy/controller.yaml").read_text()
        self.assertIn("--timeout-keep-alive, \"30\"", controller)

        route = (root / "deploy/controller-route.yaml").read_text()
        policies = [document for document in route.split("---") if "kind: BackendTrafficPolicy" in document]
        self.assertEqual(len(policies), 1)
        policy = policies[0]
        self.assertIn("apiVersion: gateway.envoyproxy.io/v1alpha1", policy)
        self.assertIn("namespace: trafficops", policy)
        self.assertRegex(
            policy,
            r"targetRefs:\s+- group: gateway\.networking\.k8s\.io\s+kind: HTTPRoute\s+name: trafficops-panel",
        )
        match = re.search(r"connectionIdleTimeout: (\d+)s", policy)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), 15)
        self.assertLess(int(match.group(1)), 30)

    def test_replacement_must_be_ready_not_just_running(self):
        client = object.__new__(Kubernetes)
        def pod(ready):
            return {"metadata": {"name": "replacement"}, "status": {
                "phase": "Running", "conditions": [{"type": "Ready", "status": ready}]}}
        replies = iter([{"items": [pod("False")]}, {"items": [pod("True")]}])
        client.demo_pods = lambda: next(replies)
        client.deployments = lambda: [{"desired": 1, "ready": 1}]
        with patch("controller.clients.time.sleep") as sleep:
            self.assertTrue(client.wait_pod_replacement("deleted"))
        sleep.assert_called_once_with(1)

    def test_old_accepted_condition_does_not_confirm_current_route(self):
        client = object.__new__(Kubernetes)
        client.route = lambda: {
            "metadata": {"generation": 12},
            "spec": {"rules": [{"backendRefs": [
                {"name": "demo-v1", "weight": 90}, {"name": "demo-v2", "weight": 10},
            ]}]},
            "status": {"parents": [{"parentRef": {"name": "trafficops"}, "conditions": [
                {"type": "Accepted", "status": "True", "observedGeneration": 11},
                {"type": "ResolvedRefs", "status": "True", "observedGeneration": 12},
            ]}]},
        }
        client.weights = lambda: {"v1": 90, "v2": 10}
        with self.assertRaises(ClusterError):
            client.wait_route(90, 10, timeout=0.01)

    def test_current_route_requires_current_accepted_and_resolved_refs(self):
        client = object.__new__(Kubernetes)
        client.route = lambda: {
            "metadata": {"generation": 12},
            "spec": {"rules": [{"backendRefs": [
                {"name": "demo-v1", "weight": 90}, {"name": "demo-v2", "weight": 10},
            ]}]},
            "status": {"parents": [{"parentRef": {"name": "trafficops"}, "conditions": [
                {"type": "Accepted", "status": "True", "observedGeneration": 12},
                {"type": "ResolvedRefs", "status": "True", "observedGeneration": 12},
            ]}]},
        }
        self.assertEqual(client.wait_route(90, 10), {"v1": 90, "v2": 10})

    def test_weight_patch_preserves_route_matches(self):
        client = object.__new__(Kubernetes)
        client.route = lambda: {"spec": {"rules": [{"matches": [{"path": {"type": "PathPrefix", "value": "/demo"}}],
                                                        "backendRefs": [{"name": "demo-v1", "port": 8080},
                                                                        {"name": "demo-v2", "port": 8080}]}]}}
        captured = {}
        client.request = lambda method, path, body: captured.update(method=method, body=body) or {}
        client.set_weights(70, 30)
        rule = captured["body"]["spec"]["rules"][0]
        self.assertEqual(rule["matches"][0]["path"]["value"], "/demo")
        self.assertEqual({item["name"]: item["weight"] for item in rule["backendRefs"]},
                         {"demo-v1": 70, "demo-v2": 30})


class PrometheusFreshnessTests(unittest.TestCase):
    def test_computed_series_use_raw_sample_times(self):
        from controller.clients import Prometheus

        now, source_time = time.time(), time.time() - 7
        class Fixture(Prometheus):
            def __init__(self):
                super().__init__()
                self.calls = []

            def query(self, expression):
                self.calls.append(expression)
                if expression.startswith("sum by (version, status)"):
                    return [{"metric": {"version": version, "status": "200"}, "value": [now, "12"]}
                            for version in ("v1", "v2")]
                if expression.startswith("((sum by (version)"):
                    return [{"metric": {"version": version}, "value": [now, "0"]}
                            for version in ("v1", "v2")]
                if expression.startswith("histogram_quantile"):
                    return [{"metric": {"version": version}, "value": [now, "0.01"]}
                            for version in ("v1", "v2")]
                if expression.startswith("rate(node_cpu"):
                    return [{"metric": {"cpu": "0"}, "value": [now, "0.2"]}]
                if expression == "node_memory_MemAvailable_bytes":
                    return [{"metric": {}, "value": [now, "1000"]}]
                if expression.startswith("max by (version) (timestamp(trafficops_http_requests_total))"):
                    return [{"metric": {"version": version}, "value": [now, str(source_time)]}
                            for version in ("v1", "v2")]
                if expression.startswith("max by (version) (timestamp(trafficops_http_request_duration_seconds_bucket))"):
                    return [{"metric": {"version": version}, "value": [now, str(source_time)]}
                            for version in ("v1", "v2")]
                if expression.startswith("max(timestamp(node_cpu") or expression.startswith("max(timestamp(node_memory"):
                    return [{"metric": {}, "value": [now, str(source_time)]}]
                raise AssertionError(expression)

        client = Fixture()
        result = client.metrics()
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["series"]["requests"][0]["sample_time"], source_time)
        self.assertEqual(result["latest_sample_time"], source_time)
        ratio_query = next(expr for expr in client.calls if expr.startswith("((sum by (version)"))
        self.assertIn(")) / clamp_min", ratio_query)
        self.assertFalse(any(expr.startswith("timestamp(sum") or expr.startswith("timestamp(rate") for expr in client.calls))
        original_query = client.query
        client.query = lambda expression: ([{"metric": {"version": version}, "value": [now, "NaN"]}
                                             for version in ("v1", "v2")] if expression.startswith("histogram_quantile")
                                            else original_query(expression))
        unknown_latency = client.metrics()
        self.assertEqual(unknown_latency["status"], "available")
        self.assertEqual(unknown_latency["series"]["latency_p95"], [])
        self.assertTrue(unknown_latency["series"]["requests"])
        client.query = lambda expression: ([{"metric": {"version": "v2"}, "value": [now, "NaN"]},
                                            {"metric": {"version": "v1"}, "value": [now, "0.01"]}]
                                           if expression.startswith("histogram_quantile")
                                           else original_query(expression))
        mixed = client.metrics()
        self.assertEqual(mixed["status"], "available")
        self.assertEqual([row["metric"]["version"] for row in mixed["series"]["latency_p95"]], ["v1"])
        client.query = lambda expression: ([{"metric": {}, "value": [now, "NaN"]}]
                                           if expression == "node_memory_MemAvailable_bytes"
                                           else original_query(expression))
        self.assertEqual(client.metrics()["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
