from __future__ import annotations

import time
from typing import Protocol

import httpx

from .models import DevinSession, SessionStatus

MAX_RATE_LIMIT_RETRIES = 4
MAX_RETRY_WAIT_SECONDS = 30.0


class DevinClient(Protocol):
    def create_session(self, prompt: str, title: str, tags: list[str]) -> DevinSession: ...

    def get_session(self, session_id: str) -> DevinSession: ...

    def append_tags(self, session_id: str, tags: list[str]) -> None: ...

    def get_session_acu(self, session_id: str) -> float | None: ...


class HttpDevinClient:
    def __init__(self, api_key: str, org_id: str, api_base: str) -> None:
        self._org_id = org_id
        self._client = httpx.Client(
            base_url=api_base,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
            transport=httpx.HTTPTransport(retries=3),
        )

    def _sessions_path(self) -> str:
        return f"/v3/organizations/{self._org_id}/sessions"

    def _send(self, method: str, url: str, **kwargs) -> httpx.Response:
        for attempt in range(MAX_RATE_LIMIT_RETRIES):
            response = self._client.request(method, url, **kwargs)
            if response.status_code == 429 and attempt < MAX_RATE_LIMIT_RETRIES - 1:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else 2.0 ** attempt
                time.sleep(min(wait, MAX_RETRY_WAIT_SECONDS))
                continue
            return response
        return response

    def create_session(self, prompt: str, title: str, tags: list[str]) -> DevinSession:
        response = self._send(
            "POST",
            self._sessions_path(),
            json={"prompt": prompt, "title": title, "tags": tags},
        )
        response.raise_for_status()
        payload = response.json()
        return DevinSession(
            session_id=payload["session_id"],
            status=SessionStatus.WORKING,
            session_url=payload.get("url"),
        )

    def get_session(self, session_id: str) -> DevinSession:
        response = self._send("GET", f"{self._sessions_path()}/{session_id}")
        response.raise_for_status()
        return _parse_session(session_id, response.json())

    def append_tags(self, session_id: str, tags: list[str]) -> None:
        response = self._send(
            "POST",
            f"{self._sessions_path()}/{session_id}/tags",
            json={"tags": tags},
        )
        response.raise_for_status()

    def get_session_acu(self, session_id: str) -> float | None:
        try:
            response = self._send(
                "GET",
                f"/v3/consumption/organizations/{self._org_id}/sessions/{session_id}",
            )
            response.raise_for_status()
            return _extract_acu(response.json())
        except (httpx.HTTPError, ValueError, KeyError):
            return None

    def get_usage_metrics(self) -> dict | None:
        try:
            response = self._send(
                "GET", f"/v3/metrics/organizations/{self._org_id}/usage"
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else None
        except (httpx.HTTPError, ValueError):
            return None

    def close(self) -> None:
        self._client.close()


def _parse_session(session_id: str, payload: dict) -> DevinSession:
    status = SessionStatus.parse(payload.get("status_enum") or payload.get("status"))
    pull_request = payload.get("pull_request") or {}
    return DevinSession(
        session_id=payload.get("session_id") or session_id,
        status=status,
        session_url=payload.get("url"),
        pr_url=pull_request.get("url"),
        acu_cost=_extract_acu(payload),
    )


def _extract_acu(payload: dict) -> float | None:
    for key in ("acu_cost", "acus", "acu", "total_acus", "consumed_acus"):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None
