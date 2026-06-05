from __future__ import annotations

import json
from pathlib import Path

from .config import Config
from .github_client import GitHubClient
from .devin_client import DevinClient
from .models import DevinSession, Issue, IssueComment, SessionStatus


class MockGitHubClient:
    def __init__(self, issues: list[dict]) -> None:
        self._issues = [
            Issue(
                number=item["number"],
                title=item["title"],
                body=item.get("body", ""),
                url=item.get("url", ""),
                labels=item.get("labels", []),
            )
            for item in issues
        ]
        self._comments: dict[int, list[str]] = {
            item["number"]: list(item.get("existing_comments", [])) for item in issues
        }

    def list_labeled_issues(self, label: str) -> list[Issue]:
        return [issue for issue in self._issues if label in issue.labels]

    def list_issue_comments(self, issue_number: int) -> list[IssueComment]:
        return [IssueComment(body=body) for body in self._comments.get(issue_number, [])]

    def create_issue_comment(self, issue_number: int, body: str) -> None:
        self._comments.setdefault(issue_number, []).append(body)


class MockDevinClient:
    def __init__(self, issues: list[dict]) -> None:
        self._by_session: dict[str, dict] = {}
        self._by_issue: dict[int, dict] = {}
        for item in issues:
            session = item["session"]
            self._by_session[session["session_id"]] = session
            self._by_issue[item["number"]] = session

    def create_session(self, prompt: str, title: str, tags: list[str]) -> DevinSession:
        issue_number = _issue_number_from_tags(tags)
        session = self._by_issue[issue_number]
        return DevinSession(
            session_id=session["session_id"],
            status=SessionStatus.WORKING,
            session_url=session.get("session_url"),
        )

    def get_session(self, session_id: str) -> DevinSession:
        session = self._by_session[session_id]
        return DevinSession(
            session_id=session_id,
            status=SessionStatus.parse(session.get("status")),
            session_url=session.get("session_url"),
            pr_url=session.get("pr_url"),
            acu_cost=session.get("acu_cost"),
            duration_seconds=session.get("duration_seconds"),
        )

    def append_tags(self, session_id: str, tags: list[str]) -> None:
        return None

    def get_session_acu(self, session_id: str) -> float | None:
        return self._by_session[session_id].get("acu_cost")


def build_mock_clients(config: Config) -> tuple[GitHubClient, DevinClient]:
    data = json.loads(Path(config.fixtures_path).read_text(encoding="utf-8"))
    issues = data["issues"]
    return MockGitHubClient(issues), MockDevinClient(issues)


def _issue_number_from_tags(tags: list[str]) -> int:
    marker = "-issue-"
    for tag in tags:
        if marker in tag:
            return int(tag.rsplit(marker, 1)[1])
    raise ValueError("no issue tag present")
