from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    devin_api_key: str
    devin_org_id: str
    github_token: str
    fork_repo: str
    issue_label: str
    devin_api_base: str
    github_api_base: str

    @property
    def session_tag_prefix(self) -> str:
        return "superset-autofix"


def _require(name: str, mock: bool) -> str:
    value = os.environ.get(name, "").strip()
    if not value and not mock:
        raise ConfigError(f"missing required environment variable: {name}")
    return value


def load_config(mock: bool = False) -> Config:
    return Config(
        devin_api_key=_require("DEVIN_API_KEY", mock),
        devin_org_id=_require("DEVIN_ORG_ID", mock),
        github_token=_require("GITHUB_TOKEN", mock),
        fork_repo=os.environ.get("FORK_REPO", "zkabyken/superset").strip(),
        issue_label=os.environ.get("ISSUE_LABEL", "autofix").strip(),
        devin_api_base=os.environ.get("DEVIN_API_BASE", "https://api.devin.ai").strip(),
        github_api_base=os.environ.get("GITHUB_API_BASE", "https://api.github.com").strip(),
    )
