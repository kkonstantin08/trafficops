import json
import threading
import unittest
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from io import StringIO
from urllib.request import urlopen

from demo.app import handler_for


class DemoAppTest(unittest.TestCase):
    def setUp(self):
        self.start_server("v1")

    def start_server(self, version, force_errors=False):
        self.logs = StringIO()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), handler_for(version, self.logs, force_errors)
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def get(self, path):
        with urlopen(self.base_url + path, timeout=2) as response:
            return response.status, response.read().decode()

    def test_versioned_json_and_region(self):
        status, body = self.get("/demo/region/east?request_id=req-123&run_id=run-456")
        self.assertEqual(status, 200)
        self.assertEqual(
            json.loads(body),
            {
                "service": "trafficops-demo",
                "version": "v1",
                "region": "east",
                "request_id": "req-123",
                "run_id": "run-456",
            },
        )

    def test_v2_response_is_distinguishable(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.start_server("v2")
        status, body = self.get("/demo")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["version"], "v2")

    def test_forced_5xx_updates_metrics_and_error_log(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.start_server("v2", force_errors=True)
        with self.assertRaises(HTTPError) as raised:
            self.get("/demo?request_id=req-500&run_id=run-500")
        raised.exception.close()
        _, metrics = self.get("/metrics")
        self.assertIn('trafficops_http_requests_total{version="v2",status="500"} 1', metrics)
        entries = [json.loads(line) for line in self.logs.getvalue().splitlines()]
        error_entries = [entry for entry in entries if entry.get("request_id") == "req-500"]
        self.assertEqual([entry["event"] for entry in error_entries], ["access", "error"])
        self.assertEqual(error_entries[-1]["request_id"], "req-500")

    def test_health_and_metrics_are_excluded_from_user_counter(self):
        self.get("/healthz")
        self.get("/metrics")
        self.get("/demo")
        _, metrics = self.get("/metrics")
        self.assertIn('trafficops_http_requests_total{version="v1",status="200"} 1', metrics)

    def test_access_log_contains_request_markers(self):
        self.get("/demo?request_id=req-123&run_id=run-456")
        entries = [json.loads(line) for line in self.logs.getvalue().splitlines()]
        self.assertEqual(entries[-1]["request_id"], "req-123")
        self.assertEqual(entries[-1]["run_id"], "run-456")

    def test_error_switch_can_change_without_restarting_handler(self):
        enabled = [False]
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.start_server("v2", force_errors=lambda: enabled[0])
        self.get("/demo")
        enabled[0] = True
        with self.assertRaises(HTTPError) as raised:
            self.get("/demo")
        raised.exception.close()


if __name__ == "__main__":
    unittest.main()
