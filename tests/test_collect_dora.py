import unittest
from datetime import datetime, timezone

from scripts.collect_dora import build_report


class BuildReportTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)

    def test_computes_four_metrics_from_deployment_records(self):
        report = build_report(
            "owner/repo",
            self.now,
            90,
            [
                {"deployed_at": "2026-09-20T12:00:00Z"},
                {"deployed_at": "2026-09-27T12:00:00Z"},
            ],
            [
                {"first_commit_at": "2026-09-19T12:00:00Z", "deployed_at": "2026-09-20T12:00:00Z", "labels": []},
                {"first_commit_at": "2026-09-25T12:00:00Z", "deployed_at": "2026-09-27T12:00:00Z", "labels": ["change-failure"]},
            ],
            [{"created_at": "2026-09-27T10:00:00Z", "closed_at": "2026-09-27T14:00:00Z"}],
        )

        self.assertEqual(report["summary"]["lead_time_hours"], 36)
        self.assertEqual(report["summary"]["deployment_frequency_per_week"], round(2 / (90 / 7), 2))
        self.assertEqual(report["summary"]["mttr_hours"], 4)
        self.assertEqual(report["summary"]["change_failure_rate"], 0.5)
        self.assertEqual(report["summary"]["failed_changes"], 1)

    def test_missing_instrumentation_is_not_reported_as_zero_performance(self):
        report = build_report("owner/repo", self.now, 90, [], [], [])

        self.assertEqual(report["coverage"], "no-production-deployments")
        self.assertIsNone(report["summary"]["lead_time_hours"])
        self.assertIsNone(report["summary"]["deployment_frequency_per_week"])
        self.assertIsNone(report["summary"]["mttr_hours"])
        self.assertIsNone(report["summary"]["change_failure_rate"])

    def test_change_failure_label_matching_is_case_insensitive(self):
        report = build_report(
            "owner/repo",
            self.now,
            90,
            [{"deployed_at": "2026-09-20T12:00:00Z"}],
            [{"first_commit_at": "2026-09-19T12:00:00Z", "deployed_at": "2026-09-20T12:00:00Z", "labels": ["Change-Failure"]}],
            [],
        )

        self.assertEqual(report["summary"]["change_failure_rate"], 1)


if __name__ == "__main__":
    unittest.main()