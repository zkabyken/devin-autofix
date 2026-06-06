from __future__ import annotations

import time
from typing import Protocol

import httpx

from .config import Config
from .models import RunReport

GAUGE = 3


class MetricsSink(Protocol):
    def record_run(self, report: RunReport) -> None: ...


class NullMetricsSink:
    def record_run(self, report: RunReport) -> None:
        return None


class DatadogMetricsSink:
    def __init__(self, api_key: str, site: str, tags: list[str]) -> None:
        self._tags = tags
        self._client = httpx.Client(
            base_url=f"https://api.{site}",
            headers={"DD-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=15.0,
            transport=httpx.HTTPTransport(retries=2),
        )

    def record_run(self, report: RunReport) -> None:
        timestamp = int(time.time())
        series = [
            self._gauge("devin_autofix.issues", report.total, timestamp),
            self._gauge("devin_autofix.dispatched", report.dispatched, timestamp),
            self._gauge("devin_autofix.pull_requests", report.pull_requests, timestamp),
            self._gauge("devin_autofix.success_rate", report.success_rate, timestamp),
            self._gauge("devin_autofix.acu_cost", report.total_acu_cost, timestamp),
        ]
        try:
            self._client.post("/api/v2/series", json={"series": series})
        except httpx.HTTPError:
            return None

    def _gauge(self, metric: str, value: float, timestamp: int) -> dict:
        return {
            "metric": metric,
            "type": GAUGE,
            "points": [{"timestamp": timestamp, "value": float(value)}],
            "tags": self._tags,
        }


def build_metrics_sink(config: Config) -> MetricsSink:
    if not config.datadog_api_key:
        return NullMetricsSink()
    return DatadogMetricsSink(
        api_key=config.datadog_api_key,
        site=config.datadog_site,
        tags=[f"repo:{config.fork_repo}", f"label:{config.issue_label}"],
    )
