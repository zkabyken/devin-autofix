# devin-autofix

An autonomous issue-fixing pipeline. A containerized orchestrator reads GitHub issues labeled `autofix` on a target repository and opens one Devin session per issue. Devin fixes the code, runs tests and opens a pull request. The orchestrator tracks every session to completion, comments the pull request back on the issue and writes an observability report.

## How it works

1. List open issues with the configured label.
2. For each issue, open a tagged Devin session running the autofix playbook (issues are processed in parallel up to a configurable cap).
3. Poll the session and stop as soon as the pull request appears.
4. Comment the result back on the issue and record it in the report.

The orchestrator is deliberately thin. It only calls the GitHub API and the Devin API over HTTP. It never runs git and never writes fixes itself. All code reasoning happens inside Devin. A marker comment on each issue makes runs idempotent, so a session is never opened twice and a crashed run reconciles on the next pass.

## Run

Mock mode runs the whole pipeline offline from committed fixtures, with no credentials and no cost. This is the recommended way to review it.

```
docker compose run --rm autofix-mock
```

Live mode reads real issues and opens real Devin sessions. Copy `.env.example` to `.env` and fill in the values first.

```
cp .env.example .env
docker compose run --rm autofix
```

Both modes write `report.json` and `report.md` into `./out`.

## Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `DEVIN_API_KEY` | yes | | Devin API bearer token |
| `DEVIN_ORG_ID` | yes | | Devin organization id for the v3 API |
| `GITHUB_TOKEN` | yes | | GitHub token with access to the repository |
| `FORK_REPO` | no | `zkabyken/superset` | Repository scanned for labeled issues |
| `ISSUE_LABEL` | no | `autofix` | Label that marks an issue for fixing |
| `MAX_PARALLEL_SESSIONS` | no | `3` | Maximum Devin sessions handled concurrently |
| `DD_API_KEY` | no | | Enables the Datadog metrics sink when set |

Configuration is environment variables only. The scheduled and manual GitHub Action in `.github/workflows/autofix.yml` reads `DEVIN_API_KEY`, `DEVIN_ORG_ID` and a PAT named `GH_TOKEN` from repository secrets.
