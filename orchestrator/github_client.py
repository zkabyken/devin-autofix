from __future__ import annotations

from typing import Protocol

import httpx

from .models import Issue, IssueComment


class GitHubClient(Protocol):
    def list_labeled_issues(self, label: str) -> list[Issue]: ...

    def list_issue_comments(self, issue_number: int) -> list[IssueComment]: ...

    def create_issue_comment(self, issue_number: int, body: str) -> None: ...

    def find_pull_request_for_branch(self, branch: str) -> str | None: ...


class HttpGitHubClient:
    def __init__(self, token: str, repo: str, api_base: str) -> None:
        self._repo = repo
        self._client = httpx.Client(
            base_url=api_base,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
            transport=httpx.HTTPTransport(retries=3),
        )

    def list_labeled_issues(self, label: str) -> list[Issue]:
        issues: list[Issue] = []
        page = 1
        while True:
            response = self._client.get(
                f"/repos/{self._repo}/issues",
                params={
                    "labels": label,
                    "state": "open",
                    "per_page": 100,
                    "page": page,
                },
            )
            response.raise_for_status()
            batch = response.json()
            if not batch:
                break
            for item in batch:
                if "pull_request" in item:
                    continue
                issues.append(_parse_issue(item))
            page += 1
        return issues

    def list_issue_comments(self, issue_number: int) -> list[IssueComment]:
        comments: list[IssueComment] = []
        page = 1
        while True:
            response = self._client.get(
                f"/repos/{self._repo}/issues/{issue_number}/comments",
                params={"per_page": 100, "page": page},
            )
            response.raise_for_status()
            batch = response.json()
            if not batch:
                break
            comments.extend(IssueComment(body=item.get("body") or "") for item in batch)
            page += 1
        return comments

    def create_issue_comment(self, issue_number: int, body: str) -> None:
        response = self._client.post(
            f"/repos/{self._repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        response.raise_for_status()

    def find_pull_request_for_branch(self, branch: str) -> str | None:
        owner = self._repo.split("/")[0]
        response = self._client.get(
            f"/repos/{self._repo}/pulls",
            params={"head": f"{owner}:{branch}", "state": "all", "per_page": 1},
        )
        response.raise_for_status()
        pulls = response.json()
        if not pulls:
            return None
        return pulls[0].get("html_url")

    def close(self) -> None:
        self._client.close()


def _parse_issue(item: dict) -> Issue:
    return Issue(
        number=item["number"],
        title=item.get("title") or "",
        body=item.get("body") or "",
        url=item.get("html_url") or "",
        labels=[label["name"] for label in item.get("labels", [])],
    )
