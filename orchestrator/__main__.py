from __future__ import annotations

import argparse

from . import pipeline, reporting
from .config import load_config
from .devin_client import DevinClient, HttpDevinClient
from .github_client import GitHubClient, HttpGitHubClient


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


def _supplementary_metrics(devin: DevinClient) -> dict | None:
    fetch = getattr(devin, "get_usage_metrics", None)
    return fetch() if callable(fetch) else None


def main() -> None:
    args = _parse_args()
    config = load_config(mock=args.mock)
    github, devin = _build_clients(args.mock, config)
    report = pipeline.run(github, devin, config)
    markdown = reporting.write_reports(report, config, _supplementary_metrics(devin))
    print(markdown)


if __name__ == "__main__":
    main()
