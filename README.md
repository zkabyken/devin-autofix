# devin-autofix

An autonomous issue-fixing pipeline. A containerized orchestrator reads GitHub issues labeled `autofix` on a fork and creates a Devin session for each one. Devin clones the fork, fixes the code, runs tests and opens a pull request. The orchestrator polls every session to completion, comments the PR URL back on the issue and writes an observability report.

## Architecture

(to be completed)

## Run

(to be completed)

## Configuration

(to be completed)
