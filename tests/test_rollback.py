import math
import unittest

from controller.rollback import evaluate_canary


POLICY = {
    "window_seconds": 60,
    "min_requests": 30,
    "error_threshold": 0.05,
    "required_breaches": 2,
    "max_sample_age_seconds": 30,
}


class CanaryDecisionTests(unittest.TestCase):
    def evaluate(self, requests=100, errors=0, sample_time=1000, target_up=1,
                 previous_breaches=0, started_at=940, now=1000):
        return evaluate_canary(
            {"requests": requests, "errors": errors, "sample_time": sample_time,
             "target_up": target_up}, POLICY, previous_breaches, started_at, now
        )

    def test_below_threshold_observes(self):
        self.assertEqual(self.evaluate(errors=5)["state"], "observe")

    def test_requires_two_consecutive_breaches(self):
        first = self.evaluate(errors=6)
        self.assertEqual((first["state"], first["breaches"]), ("observe", 1))
        second = self.evaluate(errors=6, previous_breaches=1)
        self.assertEqual((second["state"], second["breaches"]), ("rollback", 2))

    def test_exact_threshold_does_not_breach(self):
        self.assertEqual(self.evaluate(errors=5)["state"], "observe")

    def test_insufficient_stale_down_nonfinite_and_incomplete_are_unknown(self):
        self.assertEqual(self.evaluate(requests=29)["state"], "unknown")
        self.assertEqual(self.evaluate(sample_time=969)["state"], "unknown")
        self.assertEqual(self.evaluate(target_up=0)["state"], "unknown")
        self.assertEqual(self.evaluate(errors=math.nan)["state"], "unknown")
        self.assertEqual(self.evaluate(started_at=950)["state"], "unknown")


if __name__ == "__main__":
    unittest.main()
