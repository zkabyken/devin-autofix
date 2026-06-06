from __future__ import annotations

import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from .config import Config
from .devin_client import DevinClient
from .github_client import GitHubClient
from .models import DevinSession, Issue, IssueComment, LedgerRow, RunReport, SessionStatus

DISPATCH_MARKER_PREFIX = "devin-autofix:issue-"
RESULT_MARKER_PREFIX = "devin-autofix:result-issue-"


def run(github: GitHubClient, devin: DevinClient, config: Config) -> RunReport:
    issues = github.list_labeled_issues(config.issue_label)
    workers = min(config.max_parallel_sessions, len(issues)) or 1
    _log(
        f"found {len(issues)} issue(s) labeled '{config.issue_label}', "
        f"processing up to {workers} in parallel"
    )
    rows: list[LedgerRow] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_handle_issue, issue, github, devin, config): issue
            for issue in issues
        }
        for future in as_completed(futures):
            issue = futures[future]
            try:
                rows.append(future.result())
            except Exception as error:
                _log(f"#{issue.number} failed: {error}")
                rows.append(_error_row(issue))
    rows.sort(key=lambda row: row.issue_number)
    return RunReport(rows=rows)


def _handle_issue(
    issue: Issue,
    github: GitHubClient,
    devin: DevinClient,
    config: Config,
) -> LedgerRow:
    comments = github.list_issue_comments(issue.number)
    session_id = _existing_session_id(comments, issue.number)
    result_posted = _has_result_marker(comments, issue.number)

    if session_id is None:
        session_id = _dispatch(issue, github, devin, config)
    else:
        _log(f"#{issue.number} reconciling existing session {session_id}")

    session, pr_url, observed_seconds = _await_terminal(
        issue.number, github, devin, session_id, config
    )
    duration = session.duration_seconds if session.duration_seconds is not None else observed_seconds
    acu_cost = session.acu_cost if session.acu_cost is not None else devin.get_session_acu(session_id)

    definitive = bool(pr_url) or session.status.is_definitive
    if definitive and not result_posted:
        github.create_issue_comment(issue.number, _result_comment(issue, session, pr_url))
        _log(f"#{issue.number} result comment posted (pr={pr_url or 'none'})")

    return LedgerRow(
        issue_number=issue.number,
        issue_title=issue.title,
        session_id=session_id,
        status=session.status.value,
        pr_url=pr_url,
        duration_seconds=duration,
        acu_cost=acu_cost,
    )


def _dispatch(
    issue: Issue,
    github: GitHubClient,
    devin: DevinClient,
    config: Config,
) -> str:
    prompt = _render_playbook(issue, config)
    title = f"autofix #{issue.number}: {issue.title}"
    tags = [config.session_tag_prefix, config.issue_tag(issue.number)]
    session = devin.create_session(prompt=prompt, title=title, tags=tags)
    github.create_issue_comment(issue.number, _dispatch_comment(issue, session))
    _log(f"#{issue.number} dispatched session {session.session_id}")
    return session.session_id


def _await_terminal(
    issue_number: int,
    github: GitHubClient,
    devin: DevinClient,
    session_id: str,
    config: Config,
) -> tuple[DevinSession, str | None, float | None]:
    start = time.monotonic()
    deadline = start + config.poll_timeout_seconds
    branch = _branch(issue_number)
    waited = False
    last: DevinSession | None = None
    last_status: str | None = None

    while True:
        try:
            session = devin.get_session(session_id)
            last = session
            if session.status.value != last_status:
                _log(f"#{issue_number} session {session_id} status={session.status.value}")
                last_status = session.status.value
            elapsed = time.monotonic() - start if waited else None
            if session.pr_url:
                return session, session.pr_url, elapsed
            pr_url = github.find_pull_request_for_branch(branch)
            if pr_url:
                _log(f"#{issue_number} pull request detected, stopping poll")
                return session, pr_url, elapsed
            if session.status.is_terminal:
                return session, None, elapsed
        except httpx.HTTPError as error:
            _log(f"#{issue_number} poll error: {error}")

        if time.monotonic() >= deadline:
            _log(f"#{issue_number} poll timed out after {config.poll_timeout_seconds:.0f}s")
            session = last or _unknown_session(session_id)
            return session, github.find_pull_request_for_branch(branch), time.monotonic() - start

        waited = True
        time.sleep(config.poll_interval_seconds)


def _existing_session_id(comments: list[IssueComment], issue_number: int) -> str | None:
    pattern = re.compile(
        rf"{re.escape(DISPATCH_MARKER_PREFIX)}{issue_number}:session=(\S+?)\s*-->"
    )
    for comment in comments:
        match = pattern.search(comment.body)
        if match:
            return match.group(1)
    return None


def _has_result_marker(comments: list[IssueComment], issue_number: int) -> bool:
    marker = f"{RESULT_MARKER_PREFIX}{issue_number}"
    return any(marker in comment.body for comment in comments)


def _render_playbook(issue: Issue, config: Config) -> str:
    template = Path(config.playbook_path).read_text(encoding="utf-8")
    replacements = {
        "{{FORK_REPO}}": config.fork_repo,
        "{{ISSUE_NUMBER}}": str(issue.number),
        "{{ISSUE_TITLE}}": issue.title,
        "{{ISSUE_URL}}": issue.url,
        "{{ISSUE_BODY}}": issue.body,
    }
    rendered = template
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    return rendered


def _branch(issue_number: int) -> str:
    return f"autofix/issue-{issue_number}"


def _unknown_session(session_id: str) -> DevinSession:
    return DevinSession(session_id=session_id, status=SessionStatus.UNKNOWN)


def _error_row(issue: Issue) -> LedgerRow:
    return LedgerRow(
        issue_number=issue.number,
        issue_title=issue.title,
        session_id=None,
        status="error",
        pr_url=None,
        duration_seconds=None,
        acu_cost=None,
    )


def _dispatch_comment(issue: Issue, session: DevinSession) -> str:
    marker = f"<!-- {DISPATCH_MARKER_PREFIX}{issue.number}:session={session.session_id} -->"
    link = session.session_url or session.session_id
    return f"{marker}\nDevin autofix session dispatched: {link}"


def _result_comment(issue: Issue, session: DevinSession, pr_url: str | None) -> str:
    marker = f"<!-- {RESULT_MARKER_PREFIX}{issue.number} -->"
    if pr_url:
        body = f"Devin opened a pull request: {pr_url}"
    else:
        body = (
            f"Devin session {session.session_id} ended with status "
            f"'{session.status.value}' and no pull request."
        )
    return f"{marker}\n{body}"


def _log(message: str) -> None:
    print(f"[autofix] {message}", file=sys.stderr, flush=True)
