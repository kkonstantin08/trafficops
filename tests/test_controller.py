import tempfile
import unittest

from fastapi.testclient import TestClient

from controller.api import create_app, password_hash, password_matches
from controller.store import Store


class FakePlane:
    def __init__(self):
        self.called = []

    def overview(self):
        return {"release": {"status": "stable"}, "metrics": {"status": "unavailable", "updated_at": None}}

    def logs(self, marker, limit):
        return {"status": "available", "entries": [], "updated_at": 1}

    def start_traffic(self, **kwargs):
        self.called.append(("traffic", kwargs))
        return {"status": "running"}

    def stop_traffic(self):
        return {"status": "stopped"}

    def start_release(self):
        self.called.append(("release",))
        return {"status": "succeeded"}

    def set_weight(self, percent):
        return {"percent": percent}

    def rollback(self):
        return {"status": "succeeded"}

    def complete_release(self):
        return {"status": "succeeded"}

    def set_errors(self, enabled):
        return {"enabled": enabled}

    def restart_pod(self):
        return {"status": "succeeded"}


class ControllerSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.plane = FakePlane()
        self.client = TestClient(create_app(self.plane, Store(self.temp.name + "/state.db"),
                                            password_hash("test-secret", "1234567890abcdef1234567890abcdef"),
                                            "http://trafficops.local", start_on_lifespan=False))
        self.origin = {"Origin": "http://trafficops.local"}

    def tearDown(self):
        self.temp.cleanup()

    def login(self):
        response = self.client.post("/api/login", json={"password": "test-secret"}, headers=self.origin)
        self.assertEqual(response.status_code, 200)
        return response.json()["csrf"]

    def test_control_rejects_missing_session_origin_and_csrf(self):
        payload = {"rate": 1, "duration": 1, "path": "/demo"}
        self.assertEqual(self.client.post("/api/traffic/start", json=payload, headers=self.origin).status_code, 401)
        self.login()
        self.assertEqual(self.client.post("/api/traffic/start", json=payload,
                                          headers={"Origin": "http://evil.example", "X-CSRF-Token": "any"}).status_code, 403)
        self.assertEqual(self.client.post("/api/traffic/start", json=payload).status_code, 403)
        self.assertEqual(self.client.post("/api/traffic/start", json=payload, headers=self.origin).status_code, 403)
        self.assertEqual(self.plane.called, [])

    def test_control_requires_csrf_and_rejects_arbitrary_url(self):
        csrf = self.login()
        headers = {**self.origin, "X-CSRF-Token": csrf}
        response = self.client.post("/api/traffic/start", json={"rate": 1, "duration": 1,
                                        "path": "http://example.com"}, headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.plane.called, [])

    def test_bounded_traffic_action_reaches_control_plane(self):
        csrf = self.login()
        response = self.client.post("/api/traffic/start", json={"rate": 1, "duration": 1,
                                       "path": "/demo/region/east"},
                                    headers={**self.origin, "X-CSRF-Token": csrf})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.plane.called, [("traffic", {"rate": 1, "duration": 1,
                                                             "path": "/demo/region/east"})])

    def test_password_hash_round_trips_secret_file_content(self):
        encoded = password_hash("test-secret", "1234567890abcdef1234567890abcdef")
        self.assertTrue(password_matches("test-secret", encoded + "\n"))
        self.assertFalse(password_matches("other", encoded))


if __name__ == "__main__":
    unittest.main()
