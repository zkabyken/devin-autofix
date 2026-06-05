from __future__ import annotations

from typing import Protocol

import httpx

from .models import DevinSession, SessionStatus


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
        )

    def _sessions_path(self) -> str:
        return f"/v3/organizations/{self._org_id}/sessions"

    def create_session(self, prompt: str, title: str, tags: list[str]) -> DevinSession:
        response = self._client.post(
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
        response = self._client.get(f"{self._sessions_path()}/{session_id}")
        response.raise_for_status()
        return _parse_session(session_id, response.json())

    def append_tags(self, session_id: str, tags: list[str]) -> None:
        response = self._client.post(
            f"{self._sessions_path()}/{session_id}/tags",
            json={"tags": tags},
        )
        response.raise_for_status()

    def get_session_acu(self, session_id: str) -> float | None:
        try:
            response = self._client.get(
                f"/v3/consumption/organizations/{self._org_id}/sessions/{session_id}"
            )
            response.raise_for_status()
            return _extract_acu(response.json())
        except (httpx.HTTPError, ValueError, KeyError):
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
