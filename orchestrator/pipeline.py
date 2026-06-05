from __future__ import annotations

import time
from pathlib import Path

from .config import Config
from .devin_client import DevinClient
from .github_client import GitHubClient
from .models import DevinSession, Issue, LedgerRow, RunReport, SessionStatus

MARKER_PREFIX = "devin-autofix:issue-"


def run(github: GitHubClient, devin: DevinClient, config: Config) -> RunReport:
    issues = github.list_labeled_issues(config.issue_label)
    rows = [_handle_issue(issue, github, devin, config) for issue in issues]
    return RunReport(rows=rows)


def _handle_issue(
    issue: Issue,
    github: GitHubClient,
    devin: DevinClient,
    config: Config,
) -> LedgerRow:
    if _already_handled(issue, github):
        return _skipped_row(issue)

    prompt = _render_playbook(issue, config)
    title = f"autofix #{issue.number}: {issue.title}"
    tags = [config.session_tag_prefix, config.issue_tag(issue.number)]

    session = devin.create_session(prompt=prompt, title=title, tags=tags)
    github.create_issue_comment(issue.number, _dispatch_comment(issue, session))

    started = time.monotonic()
    session = _poll(devin, session.session_id, config)
    elapsed = (
        session.duration_seconds
        if session.duration_seconds is not None
        else time.monotonic() - started
    )

    acu_cost = session.acu_cost
    if acu_cost is None:
        acu_cost = devin.get_session_acu(session.session_id)

    github.create_issue_comment(issue.number, _result_comment(session))

    return LedgerRow(
        issue_number=issue.number,
        issue_title=issue.title,
        session_id=session.session_id,
        status=session.status.value,
        pr_url=session.pr_url,
        duration_seconds=elapsed,
        acu_cost=acu_cost,
    )


def _poll(devin: DevinClient, session_id: str, config: Config) -> DevinSession:
    deadline = time.monotonic() + config.poll_timeout_seconds
    while True:
        session = devin.get_session(session_id)
        if session.status.is_terminal:
            return session
        if time.monotonic() >= deadline:
            return session
        time.sleep(config.poll_interval_seconds)


def _already_handled(issue: Issue, github: GitHubClient) -> bool:
    marker = f"{MARKER_PREFIX}{issue.number}"
    return any(marker in comment.body for comment in github.list_issue_comments(issue.number))


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


def _skipped_row(issue: Issue) -> LedgerRow:
    return LedgerRow(
        issue_number=issue.number,
        issue_title=issue.title,
        session_id=None,
        status="skipped",
        pr_url=None,
        duration_seconds=None,
        acu_cost=None,
    )


def _dispatch_comment(issue: Issue, session: DevinSession) -> str:
    marker = f"<!-- {MARKER_PREFIX}{issue.number}:session={session.session_id} -->"
    link = session.session_url or session.session_id
    return f"{marker}\nDevin autofix session dispatched: {link}"


def _result_comment(session: DevinSession) -> str:
    if session.status is SessionStatus.FINISHED and session.pr_url:
        return f"Devin opened a pull request: {session.pr_url}"
    if session.status is SessionStatus.FINISHED:
        return "Devin finished the session but did not open a pull request."
    return f"Devin session {session.session_id} ended with status '{session.status.value}' and no pull request."
