from __future__ import annotations

import argparse

from . import pipeline
from .config import load_config
from .devin_client import DevinClient, HttpDevinClient
from .github_client import GitHubClient, HttpGitHubClient
from .models import RunReport


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="orchestrator")
    parser.add_argument("--mock", action="store_true", help="run with fixture-backed clients")
    return parser.parse_args()


def _build_clients(mock: bool, config) -> tuple[GitHubClient, DevinClient]:
    if mock:
        from .mock import build_mock_clients

        return build_mock_clients(config)
    github = HttpGitHubClient(
        token=config.github_token,
        repo=config.fork_repo,
        api_base=config.github_api_base,
    )
    devin = HttpDevinClient(
        api_key=config.devin_api_key,
        org_id=config.devin_org_id,
        api_base=config.devin_api_base,
    )
    return github, devin


def _print_summary(report: RunReport) -> None:
    for row in report.rows:
        print(f"#{row.issue_number} {row.status} {row.pr_url or '-'}")
    print(
        f"issues={report.total} dispatched={report.dispatched} "
        f"prs={report.pull_requests} success_rate={report.success_rate:.0%}"
    )


def main() -> None:
    args = _parse_args()
    config = load_config(mock=args.mock)
    github, devin = _build_clients(args.mock, config)
    report = pipeline.run(github, devin, config)
    _print_summary(report)


if __name__ == "__main__":
    main()
