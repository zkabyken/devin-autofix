# devin-autofix

An autonomous issue-fixing pipeline. A containerized orchestrator reads GitHub issues labeled `autofix` on a fork and creates one Devin session per issue. Devin clones the fork, fixes the code, runs tests and opens a pull request. The orchestrator polls each session to a terminal state, comments the pull request URL back on the issue and writes an observability report.

## Architecture

The orchestrator is deliberately thin plumbing. It only calls the GitHub API and the Devin API over HTTP. It never runs git against the fork and never writes code fixes itself. All code reasoning happens inside Devin sessions. Idempotency is enforced with a marker comment on each issue so a session is never dispatched twice. Every session is tagged `superset-autofix` plus the issue number so sessions stay filterable.

## Run

Mock mode runs the full pipeline offline from committed fixtures with no credentials and no cost. This is the recommended way to review it.

```
docker compose run --rm autofix-mock
```

Live mode reads issues from the real fork and dispatches real Devin sessions. Copy `.env.example` to `.env` and fill in the values first.

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
| `GITHUB_TOKEN` | yes | | GitHub token with access to the fork |
| `FORK_REPO` | no | `zkabyken/superset` | Repository scanned for labeled issues |
| `ISSUE_LABEL` | no | `autofix` | Label that marks an issue for fixing |

Configuration is supplied through environment variables only. The scheduled and manual GitHub Action in `.github/workflows/autofix.yml` reads `DEVIN_API_KEY`, `DEVIN_ORG_ID` and a fork-scoped PAT named `GH_TOKEN` from repository secrets.
