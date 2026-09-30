import json
import tempfile
import unittest
from pathlib import Path

from scripts.find_log_marker import find_marker, record_matches


class LogMarkerTests(unittest.TestCase):
    def test_matches_cri_access_json_for_expected_version(self):
        access = {
            "event": "access",
            "request_id": "verify-123",
            "version": "v2",
        }
        cri_record = (
            "2026-09-30T09:00:00.123456789Z stdout F " + json.dumps(access)
        )

        self.assertTrue(record_matches(cri_record, "verify-123", "v2"))
        self.assertFalse(record_matches(cri_record, "verify-123", "v1"))
        self.assertFalse(record_matches("{incomplete", "verify-123", "v2"))
        error_record = json.dumps({**access, "event": "error"})
        self.assertFalse(record_matches(error_record, "verify-123", "v2"))

    def test_finds_access_json_in_finalized_fluentd_file(self):
        access = {"event": "access", "request_id": "verify-123", "version": "v2"}
        row = json.dumps(
            {**access, "cri_time": "2026-09-30T09:00:00.123456789Z", "stream": "stdout"}
        )
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "trafficops.2026093009_abc.log").write_text(
                "{incomplete\n" + row + "\n", encoding="utf-8"
            )

            self.assertTrue(find_marker(directory, "verify-123", "v2"))


if __name__ == "__main__":
    unittest.main()
