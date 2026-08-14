# Harness Run Recovery Runbook

Use this reference when `status` reports `needs_human`, `idle`, `stopped`, stale runtime state, or unclear progress.

## Read Order

1. `.harness-run/runtime.json`
2. `.harness-run/runtime.log`
3. `.harness-run/state.json`
4. `.harness-run/rounds.tsv`
5. `.harness-run/docs/handoff.md`
6. `.harness-run/docs/run-plan.md`
7. `.harness-run/docs/constraints.md`

## Common Reasons

- `blocked`: the last recorded round hit a real blocker.
- `stagnated`: supervised relaunches stopped changing progress.
- `codex_unavailable`: the configured Codex executable is not available.
- `codex_launch_failed`: the controller could not start a nested Codex session.
- `missing_state_after_success`: nested Codex exited without initializing state.
- `missing_round_artifacts`: a round updated state but did not update required handoff/progress/evidence files.
- `controller_pid_dead`: `runtime.json` said running, but the controller pid was no longer alive.
- different launch contract: a new goal/scope/verify/guard/iterations/stop condition/execution policy conflicts with an existing run.

## Recovery Rules

- Do not convert `needs_human` into an unattended relaunch without evidence.
- If the contract is different, finish/stop the old run or use `--force` only after no background controller is active.
- If state is missing, rebuild the baseline before editing.
- If `runtime.json` is stale or crashed, read `runtime.log`, `state.json`, `rounds.tsv`, and `docs/handoff.md` before restarting.
- If artifacts are missing, reconstruct the actual round from source diff and logs, update `handoff.md` plus progress/evidence, then record or block exactly one round.
- If runtime log contains sensitive data, summarize only the needed facts into docs.
- After recovery, update `handoff.md` and record one round before exiting.
