# Sync Policy

Run ID: `{{RUN_ID}}`

## Target Repo Docs Detected

{{DOCS_EVIDENCE}}

## Local-Only Records

- `.harness-run/runtime.log`
- raw command outputs with secrets or local-only data

## Repo-Sync Candidates

-

## Never Sync

- secrets
- raw private logs
- unrelated local environment dumps

## Completion Sync Checklist

- [ ] plan summary
- [ ] history summary
- [ ] release impact, if user-visible
- [ ] quality notes, if quality waterline changed
