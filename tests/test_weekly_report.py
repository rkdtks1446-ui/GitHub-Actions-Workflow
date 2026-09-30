import unittest
from datetime import datetime, timezone

from scripts.generate_weekly_report import render_report


class WeeklyReportTests(unittest.TestCase):
    def test_reports_previous_complete_week_and_formats_all_metrics(self):
        metrics = {
            "repository": "owner/repo",
            "generated_at": "2026-09-28T03:17:00Z",
            "coverage_message": "Production deployment records found.",
            "summary": {
                "lead_time_hours": 12.5,
                "deployment_frequency_per_week": 2.0,
                "mttr_hours": 3.25,
                "change_failure_rate": 0.25,
                "production_deployments": 2,
                "deployed_changes": 4,
                "failed_changes": 1,
                "resolved_incidents": 1,
            },
            "series": [{
                "week_start": "2026-09-21",
                "lead_time_hours": 10.5,
                "deployment_frequency_per_week": 3,
                "mttr_hours": 2.0,
                "change_failure_rate": 0.3333,
            }],
        }

        report = render_report(metrics)

        self.assertIn("2026-09-21 ~ 2026-09-27", report)
        self.assertIn("10.5시간", report)
        self.assertIn("3회", report)
        self.assertIn("2시간", report)
        self.assertIn("33.3%", report)
        self.assertIn("최근 90일 참고", report)

    def test_missing_week_data_is_explicit_and_missing_metrics_are_not_zero(self):
        report = render_report({
            "repository": "owner/repo",
            "generated_at": "2026-09-30T00:00:00Z",
            "coverage_message": "No production deployments.",
            "summary": {"lead_time_hours": None, "deployment_frequency_per_week": None, "mttr_hours": None, "change_failure_rate": None},
            "series": [],
        })

        self.assertIn("직전 주 데이터가 집계 파일에 없습니다", report)
        self.assertIn("| Lead Time for Changes | — |", report)
        self.assertIn("실제 배포 및 라벨 기록이 없으면 성과 수치로 해석하지 마세요.", report)


if __name__ == "__main__":
    unittest.main()