from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class SessionStatus(str, Enum):
    WORKING = "working"
    BLOCKED = "blocked"
    EXPIRED = "expired"
    FINISHED = "finished"
    SUSPEND_REQUESTED = "suspend_requested"
    SUSPEND_REQUESTED_FRONTEND = "suspend_requested_frontend"
    RESUME_REQUESTED = "resume_requested"
    RESUME_REQUESTED_FRONTEND = "resume_requested_frontend"
    RESUMED = "resumed"
    UNKNOWN = "unknown"

    @classmethod
    def parse(cls, value: str | None) -> "SessionStatus":
        if not value:
            return cls.UNKNOWN
        try:
            return cls(value)
        except ValueError:
            return cls.UNKNOWN

    @property
    def is_terminal(self) -> bool:
        return self in {SessionStatus.FINISHED, SessionStatus.EXPIRED}

    @property
    def is_success(self) -> bool:
        return self is SessionStatus.FINISHED


class Issue(BaseModel):
    number: int
    title: str
    body: str
    url: str
    labels: list[str]


class IssueComment(BaseModel):
    body: str


class DevinSession(BaseModel):
    session_id: str
    status: SessionStatus
    session_url: str | None = None
    pr_url: str | None = None
    acu_cost: float | None = None
    duration_seconds: float | None = None


class LedgerRow(BaseModel):
    issue_number: int
    issue_title: str
    session_id: str | None
    status: str
    pr_url: str | None
    duration_seconds: float | None
    acu_cost: float | None


class RunReport(BaseModel):
    rows: list[LedgerRow]

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def dispatched(self) -> int:
        return sum(1 for row in self.rows if row.session_id is not None)

    @property
    def pull_requests(self) -> int:
        return sum(1 for row in self.rows if row.pr_url)

    @property
    def success_rate(self) -> float:
        if self.dispatched == 0:
            return 0.0
        return self.pull_requests / self.dispatched

    @property
    def total_acu_cost(self) -> float:
        return sum(row.acu_cost or 0.0 for row in self.rows)

    @property
    def acu_cost_per_fix(self) -> float | None:
        if self.pull_requests == 0:
            return None
        return self.total_acu_cost / self.pull_requests

    @property
    def average_time_to_fix(self) -> float | None:
        durations = [
            row.duration_seconds
            for row in self.rows
            if row.pr_url and row.duration_seconds is not None
        ]
        if not durations:
            return None
        return sum(durations) / len(durations)
