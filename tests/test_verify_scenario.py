import importlib.util
from pathlib import Path
import unittest

module_spec = importlib.util.spec_from_file_location(
    "verify_scenario", Path(__file__).parents[1] / "scripts" / "verify-scenario.py",
)
scenario = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(scenario)
cleanup = scenario.cleanup


class FailingCleanupClient:
    def __init__(self):
        self.calls = []

    def post(self, path, payload=None):
        self.calls.append((path, payload))
        if path == "/api/traffic/stop":
            raise RuntimeError("simulated cleanup error")
        return {"status": "succeeded"}


class ScenarioCleanupTests(unittest.TestCase):
    def test_cleanup_continues_after_first_restore_action_fails(self):
        client = FailingCleanupClient()
        errors = cleanup(client)
        self.assertEqual(len(errors), 1)
        self.assertIn("stop traffic", errors[0])
        self.assertEqual([path for path, _ in client.calls], [
            "/api/traffic/stop", "/api/incident/errors", "/api/release/rollback", "/api/logout",
        ])
        self.assertEqual(client.calls[1][1], {"enabled": False})


if __name__ == "__main__":
    unittest.main()
