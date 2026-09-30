import json
import math
import os
import ssl
from concurrent.futures import ThreadPoolExecutor
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ClusterError(RuntimeError):
    pass


class Kubernetes:
    """Small service-account client. Every path and resource name is server-owned."""
    def __init__(self, base=None, token_path="/var/run/secrets/kubernetes.io/serviceaccount/token",
                 ca_path="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt", opener=urlopen):
        self.base = (base or os.getenv("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc"))
        if not self.base.startswith("http"):
            self.base = "https://" + self.base
        port = os.getenv("KUBERNETES_SERVICE_PORT_HTTPS", "443")
        if "://" in self.base and self.base.count(":") == 1 and self.base.rsplit(":", 1)[-1].isdigit():
            pass
        elif self.base.endswith("kubernetes.default.svc"):
            self.base += ":" + port
        self.token_path, self.ca_path, self.opener = token_path, ca_path, opener

    def request(self, method, path, payload=None):
        try:
            token = open(self.token_path, encoding="utf-8").read().strip()
            context = ssl.create_default_context(cafile=self.ca_path)
            data = None if payload is None else json.dumps(payload).encode()
            request = Request(self.base + path, data=data, method=method,
                              headers={"Authorization": "Bearer " + token,
                                       "Content-Type": "application/merge-patch+json"})
            with self.opener(request, context=context, timeout=5) as response:
                body = response.read()
            return json.loads(body) if body else {}
        except (OSError, ValueError, HTTPError, URLError, TimeoutError) as exc:
            raise ClusterError(f"Kubernetes {method} request failed: {exc}") from exc

    def route(self):
        return self.request("GET", "/apis/gateway.networking.k8s.io/v1/namespaces/trafficops/httproutes/demo-route")

    def weights(self):
        refs = self.route()["spec"]["rules"][0]["backendRefs"]
        found = {ref["name"]: int(ref.get("weight", 1)) for ref in refs}
        if set(found) != {"demo-v1", "demo-v2"} or found["demo-v1"] + found["demo-v2"] != 100:
            raise ClusterError("demo-route has unexpected backends or weights")
        return {"v1": found["demo-v1"], "v2": found["demo-v2"]}

    def set_weights(self, v1, v2):
        if not all(isinstance(value, int) and value >= 0 for value in (v1, v2)) or v1 + v2 != 100:
            raise ValueError("route weights must be nonnegative integers totaling 100")
        route = self.route()
        rules = route.get("spec", {}).get("rules", [])
        refs = rules[0].get("backendRefs", []) if rules else []
        if {ref.get("name") for ref in refs} != {"demo-v1", "demo-v2"}:
            raise ClusterError("demo-route backend contract changed")
        by_name = {"demo-v1": v1, "demo-v2": v2}
        patched_rules = json.loads(json.dumps(rules))
        for rule in patched_rules:
            for ref in rule.get("backendRefs", []):
                if ref.get("name") in by_name:
                    ref["weight"] = by_name[ref["name"]]
        result = self.request("PATCH", "/apis/gateway.networking.k8s.io/v1/namespaces/trafficops/httproutes/demo-route",
                              {"spec": {"rules": patched_rules}})
        return result

    def wait_route(self, v1, v2, timeout=20):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            last = self.route()
            generation = last.get("metadata", {}).get("generation", 0)
            parents = [parent for parent in last.get("status", {}).get("parents", [])
                       if parent.get("parentRef", {}).get("name") == "trafficops"]
            def confirmed(kind):
                return any(condition.get("type") == kind and condition.get("status") == "True"
                           and int(condition.get("observedGeneration") or 0) == generation
                           for parent in parents for condition in parent.get("conditions", []))
            accepted, resolved = confirmed("Accepted"), confirmed("ResolvedRefs")
            refs = last.get("spec", {}).get("rules", [{}])[0].get("backendRefs", [])
            found = {ref.get("name"): int(ref.get("weight", 1)) for ref in refs}
            weights = {"v1": found.get("demo-v1"), "v2": found.get("demo-v2")}
            if accepted and resolved and weights == {"v1": v1, "v2": v2}:
                return weights
            time.sleep(min(1, max(0, deadline - time.time())))
        raise ClusterError("Gateway did not confirm demo-route weights")

    def deployments(self):
        items = [self.request("GET", f"/apis/apps/v1/namespaces/trafficops/deployments/{name}")
                 for name in ("demo-v1", "demo-v2")]
        return [{"name": item["metadata"]["name"], "ready": item.get("status", {}).get("readyReplicas", 0),
                 "desired": item.get("spec", {}).get("replicas", 0)} for item in items]

    def wait_deployments(self, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            deployments = self.deployments()
            if len(deployments) == 2 and all(item["desired"] > 0 and item["ready"] == item["desired"] for item in deployments):
                return deployments
            time.sleep(2)
        raise ClusterError("demo deployments did not return to their desired ready replicas")

    def set_errors(self, enabled):
        # ConfigMap has one fixed name and a fixed configuration field.
        self.request("PATCH", "/api/v1/namespaces/trafficops/configmaps/demo-v2-config",
                     {"data": {"APP_FORCE_ERRORS": "true" if enabled else "false"}})

    def restart_one_pod(self):
        data = self.demo_pods()
        pods = sorted((p for p in data.get("items", []) if p.get("status", {}).get("phase") == "Running"),
                      key=lambda p: p["metadata"]["name"])
        if not pods:
            raise ClusterError("no running demo pod is available")
        name = pods[0]["metadata"]["name"]
        self.request("DELETE", f"/api/v1/namespaces/trafficops/pods/{name}")
        return name

    def demo_pods(self):
        return self.request("GET", "/api/v1/namespaces/trafficops/pods?labelSelector=app.kubernetes.io%2Fname%3Ddemo")

    def wait_pod_replacement(self, deleted_name, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            pods = self.demo_pods().get("items", [])
            ready = [pod for pod in pods if pod.get("status", {}).get("phase") == "Running"
                     and pod["metadata"]["name"] != deleted_name]
            deployments = self.deployments()
            required = sum(item["desired"] for item in deployments)
            if deleted_name not in {pod["metadata"]["name"] for pod in pods} and len(ready) >= required:
                return True
            time.sleep(1)
        raise ClusterError("replacement demo pod did not become Running")


class Prometheus:
    def __init__(self, base="http://prometheus.observability.svc:9090", opener=urlopen):
        self.base, self.opener = base.rstrip("/"), opener

    def query(self, expression):
        url = self.base + "/api/v1/query?" + urlencode({"query": expression})
        try:
            with self.opener(url, timeout=4) as response:
                payload = json.loads(response.read())
            if payload.get("status") != "success":
                raise ValueError("Prometheus returned an unsuccessful query")
            return payload["data"]["result"]
        except (OSError, ValueError, KeyError, TypeError, URLError, TimeoutError) as exc:
            raise ClusterError(f"Prometheus query failed: {exc}") from exc

    @staticmethod
    def sample(result):
        if len(result) != 1:
            raise ClusterError("Prometheus sample is missing or ambiguous")
        try:
            value = float(result[0]["value"][1])
        except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
            raise ClusterError("Prometheus sample is malformed") from exc
        if not math.isfinite(value):
            raise ClusterError("Prometheus sample is not finite")
        return value

    def canary_snapshot(self, window):
        # timestamp() exposes the source sample time; the HTTP query's evaluation timestamp is irrelevant.
        expressions = [
            f'sum(increase(trafficops_http_requests_total{{version="v2"}}[{window}s]))',
            f'sum(increase(trafficops_http_requests_total{{version="v2",status=~"5.."}}[{window}s])) or vector(0)',
            'max(timestamp(trafficops_http_requests_total{version="v2"}))',
            'max(timestamp(up{job="trafficops-demo-v2"}))',
            'min(up{job="trafficops-demo-v2"})',
        ]
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(self.query, expressions))
        requests = self.sample(results[0])
        errors = self.sample(results[1])
        sample_time = min(self.sample(results[2]), self.sample(results[3]))
        target_up = self.sample(results[4])
        return {"requests": requests, "errors": errors, "sample_time": sample_time, "target_up": target_up}

    def metrics(self):
        expressions = {
            "requests": "sum by (version, status) (increase(trafficops_http_requests_total[5m]))",
            "error_rate": '((sum by (version) (rate(trafficops_http_requests_total{status=~"5.."}[5m])) or on (version) (sum by (version) (rate(trafficops_http_requests_total[5m])) * 0)) / clamp_min(sum by (version) (rate(trafficops_http_requests_total[5m])), 1e-9))',
            "latency_p95": 'histogram_quantile(0.95, sum by (le, version) (rate(trafficops_http_request_duration_seconds_bucket[5m])))',
            "cpu": "rate(node_cpu_seconds_total{mode!=\"idle\"}[5m])",
            "memory": "node_memory_MemAvailable_bytes",
        }
        source_expressions = {
            "requests": 'max by (version) (timestamp(trafficops_http_requests_total))',
            "error_rate": 'max by (version) (timestamp(trafficops_http_requests_total))',
            "latency_p95": 'max by (version) (timestamp(trafficops_http_request_duration_seconds_bucket))',
            "cpu": 'max(timestamp(node_cpu_seconds_total{mode!="idle"}))',
            "memory": 'max(timestamp(node_memory_MemAvailable_bytes))',
        }
        out = {"status": "available", "updated_at": None, "latest_sample_time": None, "series": {}}
        try:
            with ThreadPoolExecutor(max_workers=len(expressions) * 2) as pool:
                future_values = {key: pool.submit(self.query, query) for key, query in expressions.items()}
                future_sources = {key: pool.submit(self.query, query) for key, query in source_expressions.items()}
                for key, future in future_values.items():
                    values = future.result()
                    sources = future_sources[key].result()
                    source_times = {row.get("metric", {}).get("version"): float(row["value"][1])
                                    for row in sources if row.get("metric", {}).get("version")}
                    global_time = float(sources[0]["value"][1]) if sources and not source_times else None
                    rows = []
                    for row in values:
                        version = row.get("metric", {}).get("version")
                        source_time = source_times.get(version, global_time)
                        if source_time is None:
                            raise ClusterError(f"raw source sample timestamp is missing for {key}")
                        try:
                            value = float(row["value"][1])
                        except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
                            raise ClusterError(f"Prometheus series is malformed for {key}") from exc
                        if not math.isfinite(value):
                            raise ClusterError(f"Prometheus series is non-finite for {key}")
                        rows.append({"metric": row.get("metric", {}), "value": row["value"],
                                     "sample_time": source_time})
                    if not rows:
                        raise ClusterError(f"Prometheus series is empty for {key}")
                    out["series"][key] = rows
            samples = [row["sample_time"] for rows in out["series"].values() for row in rows]
            if not all(math.isfinite(value) for value in samples):
                raise ClusterError("Prometheus source timestamps are not finite")
            out["latest_sample_time"] = min(samples)
            if out["latest_sample_time"] > time.time() + 5 or time.time() - out["latest_sample_time"] > 30:
                raise ClusterError("Prometheus source samples are older than 30 seconds")
            out["updated_at"] = out["latest_sample_time"]
        except (ClusterError, KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
            return {"status": "unavailable", "updated_at": None, "latest_sample_time": None,
                    "error": str(exc), "series": {}}
        return out
