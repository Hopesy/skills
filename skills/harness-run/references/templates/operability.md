# Operability

Run ID: `{{RUN_ID}}`

## Start / Stop / Resume

- launch: `{{LAUNCH_PATH}}`
- state: `{{STATE_PATH}}`
- rounds: `{{ROUNDS_PATH}}`
- runtime: `{{RUNTIME_PATH}}`
- log: `{{RUNTIME_LOG_PATH}}`

## Health Checks

-

## Logs

- Raw runtime logs stay in `runtime.log`.
- Summaries may be copied into run docs after redaction.

## Timeouts / Retry / Backoff

-

## Known Failure Modes

-

## Recovery Steps

- Read `handoff.md`, `runtime.json`, `state.json`, `rounds.tsv`, and `runtime.log`.
- Do not relaunch unattended from `needs_human` without evidence.

## Local Verification Path

-

## CI Verification Path

-
