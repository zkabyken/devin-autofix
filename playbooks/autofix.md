# Autofix Playbook

You are fixing a single GitHub issue on the fork `{{FORK_REPO}}`.

## Issue
- Number: #{{ISSUE_NUMBER}}
- Title: {{ISSUE_TITLE}}
- URL: {{ISSUE_URL}}

### Description
{{ISSUE_BODY}}

## Task
1. Clone the fork `{{FORK_REPO}}` and create a new branch named `autofix/issue-{{ISSUE_NUMBER}}`.
2. Reproduce and understand the problem described in the issue.
3. Implement the smallest correct fix. Do not make unrelated changes.
4. Run the relevant tests and the linter. Make them pass.
5. Commit with a clear message that references issue #{{ISSUE_NUMBER}}.
6. Push the branch and open a pull request against the fork's default branch.
7. The pull request description must explain the root cause and the fix and must include the line `Fixes #{{ISSUE_NUMBER}}`.

## Constraints
- Keep the change minimal and focused on this issue only.
- Do not modify CI configuration, secrets or unrelated files.
- Work autonomously. Do not pause to ask for confirmation or further instructions.
- Opening the pull request completes the task.
- If the issue cannot be fixed safely, stop and explain why instead of opening a pull request.

## Result
Return the pull request URL.
