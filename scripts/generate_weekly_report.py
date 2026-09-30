#!/usr/bin/env python3
"""Generate a Markdown report for the last complete UTC week."""

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def previous_week(metrics):
    generated_at = metrics.get("generated_at")
    report_date = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).date() if generated_at else date.today()
    this_monday = report_date - timedelta(days=report_date.weekday())
    week_start = this_monday - timedelta(days=7)
    week_end = this_monday - timedelta(days=1)
    matching = next((row for row in metrics.get("series", []) if row.get("week_start") == week_start.isoformat()), None)
    return week_start, week_end, matching


def display(value, unit=""):
    if value is None:
        return "—"
    if unit == "%":
        return f"{value * 100:.1f}%"
    if isinstance(value, float):
        value = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{value}{unit}"


def render_report(metrics):
    week_start, week_end, weekly = previous_week(metrics)
    summary = metrics.get("summary", {})
    week = weekly or {}
    repository = metrics.get("repository", "unknown/unknown")
    generated_at = metrics.get("generated_at") or "not collected yet"
    has_week_data = weekly is not None

    lines = [
        f"# DORA 주간 보고서 ({week_start.isoformat()} ~ {week_end.isoformat()})",
        "",
        f"- 저장소: `{repository}`",
        f"- 생성 시각(UTC): `{generated_at}`",
        f"- 데이터 상태: {metrics.get('coverage_message', '상태 정보 없음')}",
        "",
        "## 직전 주 지표",
        "",
        "| 지표 | 값 |",
        "| --- | ---: |",
        f"| Lead Time for Changes | {display(week.get('lead_time_hours'), '시간')} |",
        f"| Deployment Frequency | {display(week.get('deployment_frequency_per_week'), '회')} |",
        f"| MTTR | {display(week.get('mttr_hours'), '시간')} |",
        f"| Change Failure Rate | {display(week.get('change_failure_rate'), '%')} |",
        "",
        "## 최근 90일 참고",
        "",
        "| 지표 | 값 |",
        "| --- | ---: |",
        f"| Lead Time for Changes | {display(summary.get('lead_time_hours'), '시간')} |",
        f"| Deployment Frequency | {display(summary.get('deployment_frequency_per_week'), '회/주')} |",
        f"| MTTR | {display(summary.get('mttr_hours'), '시간')} |",
        f"| Change Failure Rate | {display(summary.get('change_failure_rate'), '%')} |",
        "",
        "## 표본 수",
        "",
        f"- 성공한 production 배포: {summary.get('production_deployments', 0)}건",
        f"- 배포 연결된 PR: {summary.get('deployed_changes', 0)}건",
        f"- 실패 변경으로 분류된 PR: {summary.get('failed_changes', 0)}건",
        f"- 종료된 incident: {summary.get('resolved_incidents', 0)}건",
        "",
        "> `—`는 해당 기간에 계산 가능한 관측값이 없음을 뜻합니다. 실제 배포 및 라벨 기록이 없으면 성과 수치로 해석하지 마세요.",
        "",
    ]
    if not has_week_data:
        lines.insert(7, "> 직전 주 데이터가 집계 파일에 없습니다. 초기 수집 또는 날짜 범위를 확인하세요.")
        lines.insert(8, "")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metrics = json.loads(args.input.read_text(encoding="utf-8"))
    content = render_report(metrics)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")

    week_start, _, _ = previous_week(metrics)
    dated = args.output.parent / f"{week_start.isoformat()}.md"
    dated.write_text(content, encoding="utf-8")
    print(f"Wrote {args.output} and {dated}")


if __name__ == "__main__":
    main()