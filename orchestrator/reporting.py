from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .config import Config
from .models import LedgerRow, RunReport


def build_summary(report: RunReport, supplementary: dict | None = None) -> dict:
    summary = {
        "issues": report.total,
        "dispatched": report.dispatched,
        "pull_requests": report.pull_requests,
        "success_rate": round(report.success_rate, 4),
        "average_time_to_fix_seconds": _round_optional(report.average_time_to_fix),
        "total_acu_cost": round(report.total_acu_cost, 4),
        "acu_cost_per_fix": _round_optional(report.acu_cost_per_fix),
    }
    if supplementary:
        summary["devin_metrics"] = supplementary
    return summary


def build_document(report: RunReport, supplementary: dict | None = None) -> dict:
    return {
        "summary": build_summary(report, supplementary),
        "rows": [row.model_dump() for row in report.rows],
    }


def render_markdown(report: RunReport, supplementary: dict | None = None) -> str:
    summary = build_summary(report, supplementary)
    lines = [
        "# devin-autofix run report",
        "",
        f"- Issues: {summary['issues']}",
        f"- Dispatched: {summary['dispatched']}",
        f"- Pull requests: {summary['pull_requests']}",
        f"- Success rate: {_percent(report.success_rate)}",
        f"- Average time to fix: {_duration(report.average_time_to_fix)}",
        f"- Total ACU cost: {summary['total_acu_cost']}",
        f"- ACU cost per fix: {_optional_number(report.acu_cost_per_fix)}",
        "",
        "| Issue | Status | Pull request | Duration | ACU |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(_render_row(row) for row in report.rows)
    lines.append("")
    return "\n".join(lines)


def write_reports(
    report: RunReport,
    config: Config,
    supplementary: dict | None = None,
) -> str:
    document = build_document(report, supplementary)
    markdown = render_markdown(report, supplementary)
    _write_file(config.report_json_path, json.dumps(document, indent=2) + "\n")
    _write_file(config.report_md_path, markdown)
    _write_step_summary(markdown)
    return markdown


def _write_file(path: str, content: str) -> None:
    try:
        Path(path).write_text(content, encoding="utf-8")
    except OSError as error:
        print(f"[autofix] could not write {path}: {error}", file=sys.stderr, flush=True)


def _write_step_summary(markdown: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(markdown)
            handle.write("\n")
    except OSError as error:
        print(f"[autofix] could not write step summary: {error}", file=sys.stderr, flush=True)


def _render_row(row: LedgerRow) -> str:
    pr = f"[PR]({row.pr_url})" if row.pr_url else "-"
    return (
        f"| #{row.issue_number} | {row.status} | {pr} | "
        f"{_duration(row.duration_seconds)} | {_optional_number(row.acu_cost)} |"
    )


def _round_optional(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _optional_number(value: float | None) -> str:
    return "-" if value is None else f"{value:g}"


def _percent(value: float) -> str:
    return f"{value:.0%}"


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    total = int(round(seconds))
    return f"{total // 60}m {total % 60}s"
