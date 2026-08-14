# Harness Run Collaboration Protocol

Use this reference when a harness-run task must keep engineering discipline across fresh Codex sessions.

## Core Rule

Treat `.harness-run/docs/` as the run-level collaboration record. Treat `.harness-run/*.json`, `rounds.tsv`, and `runtime.log` as the machine control plane.

Do not replace source evidence with memory. Re-read:

1. repo instructions such as `AGENTS.md`;
2. `.harness-run/launch.json`;
3. `.harness-run/state.json`;
4. `.harness-run/rounds.tsv`;
5. `.harness-run/docs/constraints.md`;
6. `.harness-run/docs/run-plan.md`;
7. `.harness-run/docs/project-architecture.md`;
8. `.harness-run/docs/handoff.md`.

## Update Cadence

Always update:

- `state.json`
- `rounds.tsv`
- `docs/handoff.md`

Update when facts change:

- `docs/progress.md`
- `docs/decisions.md`
- `docs/change-inventory.md`
- `docs/sync-policy.md`

Update only from evidence:

- `docs/project-architecture.md`
- `docs/constraints.md`
- `docs/validation-pipeline.md`

Write completion records only when the stop condition is met:

- `docs/completion.md`
- `docs/release-impact.md` when user-visible behavior changed
- target repo docs when `sync-policy.md` says to sync

## Non-Negotiables

- Keep raw logs and secrets out of Markdown docs.
- Record plan changes in `decisions.md`.
- Do not relax constraints without user instruction or higher-priority repo instructions.
- Do not leave the next session dependent on chat-only state.
