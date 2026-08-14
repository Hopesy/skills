# Persistence And Redaction

Use this reference when deciding what harness-run should write, keep local, or sync to a target repo.

## Local-Only By Default

- `.harness-run/runtime.log`
- raw command output containing secrets, accounts, tokens, local-only paths, or private logs
- transient controller state
- generated snapshots that cannot be reproduced or safely reviewed

## Safe To Summarize

- commands run
- pass/fail status
- file paths touched
- short error category
- decisions and rationale
- verification evidence without sensitive payloads

## Sync Candidate

Only sync a concise summary to target repo docs when:

- the target repo has a compatible docs structure;
- the change affects product behavior, architecture, validation, security, release notes, or history;
- `sync-policy.md` marks the destination as allowed.

## Never Persist In Markdown

- API keys, passwords, refresh tokens, session tokens, private cookies
- full JWTs or OAuth responses
- full personal inbox contents
- unrelated local environment dumps
- large vendor docs copied verbatim
