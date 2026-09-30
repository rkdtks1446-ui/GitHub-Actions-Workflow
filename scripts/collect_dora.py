#!/usr/bin/env python3
"""Collect repository-level DORA metrics from the GitHub REST API."""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
FAILURE_LABEL = "change-failure"
INCIDENT_LABEL = "incident"


def parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def iso_time(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def week_start(value):
    return (value - timedelta(days=value.weekday())).date().isoformat()


def build_report(repository, now, days, deployments, deployed_changes, incidents):
    start = now - timedelta(days=days)
    deployments = [item for item in deployments if start <= parse_time(item["deployed_at"]) <= now]
    deployed_changes = [item for item in deployed_changes if start <= parse_time(item["deployed_at"]) <= now]
    incidents = [item for item in incidents if item.get("closed_at") and start <= parse_time(item["closed_at"]) <= now]

    lead_hours = [
        (parse_time(item["deployed_at"]) - parse_time(item["first_commit_at"])).total_seconds() / 3600
        for item in deployed_changes
        if item.get("first_commit_at") and parse_time(item["deployed_at"]) >= parse_time(item["first_commit_at"])
    ]
    recovery_hours = [
        (parse_time(item["closed_at"]) - parse_time(item["created_at"])).total_seconds() / 3600
        for item in incidents
        if parse_time(item["closed_at"]) >= parse_time(item["created_at"])
    ]
    failed_changes = sum(FAILURE_LABEL in {label.lower() for label in item.get("labels", [])} for item in deployed_changes)

    first_week = parse_time(week_start(start) + "T00:00:00+00:00")
    week_count = ((now.date() - first_week.date()).days // 7) + 1
    series = []
    for offset in range(week_count):
        bucket_start = first_week + timedelta(weeks=offset)
        bucket_end = bucket_start + timedelta(weeks=1)
        weekly_deployments = [item for item in deployments if bucket_start <= parse_time(item["deployed_at"]) < bucket_end]
        weekly_changes = [item for item in deployed_changes if bucket_start <= parse_time(item["deployed_at"]) < bucket_end]
        weekly_lead = [
            (parse_time(item["deployed_at"]) - parse_time(item["first_commit_at"])).total_seconds() / 3600
            for item in weekly_changes
            if item.get("first_commit_at") and parse_time(item["deployed_at"]) >= parse_time(item["first_commit_at"])
        ]
        weekly_incidents = [item for item in incidents if bucket_start <= parse_time(item["closed_at"]) < bucket_end]
        weekly_recovery = [
            (parse_time(item["closed_at"]) - parse_time(item["created_at"])).total_seconds() / 3600
            for item in weekly_incidents
            if parse_time(item["closed_at"]) >= parse_time(item["created_at"])
        ]
        weekly_failures = sum(FAILURE_LABEL in {label.lower() for label in item.get("labels", [])} for item in weekly_changes)
        series.append({
            "week_start": bucket_start.date().isoformat(),
            "lead_time_hours": round(sum(weekly_lead) / len(weekly_lead), 2) if weekly_lead else None,
            "deployment_frequency_per_week": len(weekly_deployments),
            "mttr_hours": round(sum(weekly_recovery) / len(weekly_recovery), 2) if weekly_recovery else None,
            "change_failure_rate": round(weekly_failures / len(weekly_changes), 4) if weekly_changes else None,
        })

    has_deployments = bool(deployments)
    return {
        "schema_version": 1,
        "repository": repository,
        "generated_at": iso_time(now),
        "window_days": days,
        "coverage": "recording" if has_deployments else "no-production-deployments",
        "coverage_message": "Production deployment records found." if has_deployments else "No production deployment records yet. Configure a production environment on the deploy workflow.",
        "summary": {
            "lead_time_hours": round(sum(lead_hours) / len(lead_hours), 2) if lead_hours else None,
            "deployment_frequency_per_week": round(len(deployments) / (days / 7), 2) if has_deployments else None,
            "mttr_hours": round(sum(recovery_hours) / len(recovery_hours), 2) if recovery_hours else None,
            "change_failure_rate": round(failed_changes / len(deployed_changes), 4) if deployed_changes else None,
            "production_deployments": len(deployments),
            "deployed_changes": len(deployed_changes),
            "failed_changes": failed_changes,
            "resolved_incidents": len(recovery_hours),
        },
        "series": series,
    }


class GitHub:
    def __init__(self, token, repository):
        self.token = token
        self.repository = repository

    def get(self, path, params=None):
        url = path if path.startswith("https://") else f"{API_ROOT}{path}"
        if params:
            url += ("&" if "?" in url else "?") + urlencode(params)
        request = Request(url, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def pages(self, path, params=None):
        params = dict(params or {})
        page = 1
        while True:
            data = self.get(path, {**params, "per_page": 100, "page": page})
            items = data.get("items", []) if isinstance(data, dict) else data
            if not items:
                break
            yield from items
            if len(items) < 100:
                break
            page += 1

    def merged_pull_requests(self, start):
        query = f"repo:{self.repository} is:pr is:merged merged:>={start.date().isoformat()}"
        search_results = self.pages("/search/issues", {"q": query, "sort": "updated", "order": "desc"})
        for result in search_results:
            pull = self.get(f"/repos/{self.repository}/pulls/{result['number']}")
            commits = self.pages(pull["commits_url"])
            commit_dates = [
                parse_time(commit.get("commit", {}).get("author", {}).get("date"))
                or parse_time(commit.get("commit", {}).get("committer", {}).get("date"))
                for commit in commits
            ]
            commit_dates = [value for value in commit_dates if value]
            labels = [label["name"].lower() for label in pull.get("labels", [])]
            yield {
                "number": pull["number"],
                "merged_at": pull["merged_at"],
                "first_commit_at": iso_time(min(commit_dates)) if commit_dates else pull["created_at"],
                "merge_commit_sha": pull.get("merge_commit_sha"),
                "labels": labels,
            }

    def successful_deployments(self):
        deployments = self.pages(f"/repos/{self.repository}/deployments", {"environment": "production"})
        for deployment in deployments:
            statuses = self.pages(deployment["statuses_url"])
            latest = next(iter(statuses), None)
            if latest and latest.get("state") == "success":
                yield {
                    "id": deployment["id"],
                    "sha": deployment["sha"],
                    "deployed_at": latest["updated_at"],
                }

    def includes_change(self, merge_sha, deploy_sha):
        if merge_sha == deploy_sha:
            return True
        comparison = self.get(f"/repos/{self.repository}/compare/{merge_sha}...{deploy_sha}")
        return comparison.get("status") in ("ahead", "identical")

    def deployed_changes(self, pulls, deployments):
        changes = []
        for pull in pulls:
            if not pull.get("merge_commit_sha"):
                continue
            merged_at = parse_time(pull["merged_at"])
            candidates = sorted(
                (item for item in deployments if parse_time(item["deployed_at"]) >= merged_at),
                key=lambda item: item["deployed_at"],
            )
            for deployment in candidates:
                if self.includes_change(pull["merge_commit_sha"], deployment["sha"]):
                    changes.append({
                        "pull_request": pull["number"],
                        "first_commit_at": pull["first_commit_at"],
                        "deployed_at": deployment["deployed_at"],
                        "labels": pull["labels"],
                    })
                    break
        return changes

    def incidents(self, start):
        query = f"repo:{self.repository} is:issue label:{INCIDENT_LABEL} closed:>={start.date().isoformat()}"
        for issue in self.pages("/search/issues", {"q": query, "sort": "created", "order": "desc"}):
            if issue.get("pull_request"):
                continue
            yield {
                "created_at": issue["created_at"],
                "closed_at": issue.get("closed_at"),
            }


def collect(repository, token, days, now=None):
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    github = GitHub(token, repository)
    pulls = list(github.merged_pull_requests(start))
    deployments = list(github.successful_deployments())
    changes = github.deployed_changes(pulls, deployments)
    incidents = list(github.incidents(start))
    return build_report(repository, now, days, deployments, changes, incidents)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--days", type=int, default=90)
    args = parser.parse_args()
    repository = os.environ.get("GH_REPOSITORY")
    token = os.environ.get("GH_TOKEN")
    if not repository or not token:
        parser.error("GH_REPOSITORY and GH_TOKEN environment variables are required")
    try:
        report = collect(repository, token, args.days)
    except (HTTPError, URLError, KeyError, ValueError) as error:
        print(f"DORA collection failed: {error}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}: {report['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())