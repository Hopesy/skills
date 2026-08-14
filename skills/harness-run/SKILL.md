---
name: harness-run
description: Persistent docs-backed harness for long Codex coding tasks that need goal-only autonomous execution, inferred planning/verification, unattended improve-verify-resume loops, durable state, run-local collaboration records, background relaunch, status/stop control, or scoped multi-agent side work. Use only for explicit long-running, overnight, resumable, or autonomous execution requests, not for ordinary one-shot help or casual Q&A.
license: MIT
metadata:
  author: hopesy
  version: "1.0.0"
---

# Harness Run

Use this skill for long-running work that must survive fresh contexts, background relaunches, or planned handoffs. Do not use it for one-shot Q&A.

## When To Use

- Unattended improve-verify loops
- Overnight debugging, fixing, auditing, or shipping work
- Resume from durable state after a fresh Codex session
- Background runs that should relaunch fresh `codex exec` sessions
- Scoped multi-agent inspection, verification, or review

## What This Skill Owns

- Persistent run control through `scripts/harness_run_ctl.py`
- Durable state under `.harness-run/`
- Run-local collaboration docs under `.harness-run/docs/`
- Per-round evidence, generated knowledge, and design notes under `.harness-run/evidence/`, `.harness-run/generated/`, and `.harness-run/design/`
- Foreground and background parity
- Resume, status, stop, and handoff behavior
- One-round-at-a-time improve-verify loops

## User Entry

- `run-task`: start a durable run with one natural-language goal; `--verify` is optional
- `status`: inspect the current run in human-readable form
- `stop`: stop the current run cleanly

Normal users should not have to operate internal commands or design a full launch contract. When this skill triggers, accept a goal-only request, infer the plan, scope, metric, and verification approach from project evidence, run the helper script yourself, and report the durable state paths plus the current status. Only mention internal commands when debugging or when a fresh Codex session must reconstruct the runtime prompt manually.

Every run initializes a mini collaboration record under `.harness-run/docs/`. This record is the run-local equivalent of a project docs system: architecture snapshot, run plan, constraints, validation pipeline, progress, decisions, handoff, completion, and sync policy. If the target repo has its own `docs/`, keep `.harness-run/docs/` as the execution layer and sync only concise summaries when the run's `sync-policy.md` allows it.

## Launch Contract

Only `Goal` is required from the user. Infer these fields before starting:

- `Goal`
- `Scope`
- `Metric`
- `Direction`
- `Verify`

Optional fields:

- `Guard`
- `Iterations`
- `Stop condition`
- `Run mode`
- `Execution policy`

If a field can be inferred safely, infer it. If scope is unclear, default to the current repo or current working directory and narrow it after reading evidence. If verification is unclear, do not block launch; use plan/checklist completion with concrete evidence. Ask only when continuing would likely produce work opposite to the user's intent.

If the user explicitly says to follow a directory, plan file, roadmap, issue list, checklist, or existing project plan, treat that plan as authoritative scope and sequence. Read it, follow it, and do not renegotiate the plan unless it contradicts safety, repo instructions, or executable evidence.

Default execution policy is `workspace_write`. Do not use `danger_full_access` unless the user explicitly requests or accepts that elevated background risk; that mode injects Codex's dangerous bypass argument into nested `codex exec` sessions.

Default stop behavior:

- when `direction=pass`, the run stops once verification passes
- when `direction=complete`, the run stops once the recorded metric reaches completion
- when `verify` is provided and `metric` is omitted, the verify command itself is used as the tracked metric label
- when `verify` is omitted, use `metric=planned work checklist`, `direction=complete`, `stop_condition=complete`, and record `complete` only after the inferred or user-specified plan is satisfied with evidence
- background runs default to an iteration cap of 25 when no explicit cap is provided

## Quick Start

Background:

1. Start with `run-task`.
2. Use `status` to inspect the runtime and `stop` to end it.
3. If the process stops on `needs_human`, read `.harness-run/runtime.log`, `.harness-run/state.json`, and `.harness-run/rounds.tsv` before continuing.
4. Read `.harness-run/docs/handoff.md`, `.harness-run/docs/run-plan.md`, and `.harness-run/docs/constraints.md` before resuming work.

Foreground:

1. `run-task --foreground` prepares the durable run in the current Codex session.
2. Read the repo `AGENTS.md`, current source, build/test config, and recent logs.
3. Measure the baseline.
4. Initialize state after the baseline exists.
5. Run one focused change, verify with the command or evidence checklist, and record the result.
6. Update `.harness-run/docs/handoff.md` every round; update progress, decisions, constraints, and architecture only when facts change.
7. Repeat from persisted state.

Common commands:

```bash
python <skill-root>/scripts/harness_run_ctl.py run-task --goal "<goal>"
python <skill-root>/scripts/harness_run_ctl.py run-task --foreground --goal "<goal>"
python <skill-root>/scripts/harness_run_ctl.py run-task --goal "<goal>" --verify "<command>"
python <skill-root>/scripts/harness_run_ctl.py run-task --foreground --goal "<goal>" --verify "<command>"
python <skill-root>/scripts/harness_run_ctl.py status
python <skill-root>/scripts/harness_run_ctl.py stop
```

## Durable State

All normal run artifacts live under:

```text
<workspace_root>/.harness-run/
```

Files:

- `launch.json`: confirmed launch manifest
- `state.json`: primary recovery snapshot
- `rounds.tsv`: append-only audit trail
- `runtime.json`: background controller pid, status, and last decision
- `runtime.log`: controller and nested Codex output
- `context.json`: canonical path map for the active run
- `docs/`: run-local collaboration docs and handoff records
- `evidence/`: concise per-round evidence notes
- `generated/`: generated knowledge snapshots with source commands
- `design/`: design notes too large for the decision log

Each managed git repo may also get a git-local pointer at:

```bash
git rev-parse --git-path harness-run/pointer.json
```

That pointer resolves back to the workspace-owned `context.json`.

The run-local docs are initialized from templates in `references/templates/`. They are not a replacement for target repo docs. They are the durable execution record that lets fresh Codex sessions continue without hidden conversation state.

Core run docs:

- `project-architecture.md`
- `product-context.md`
- `run-plan.md`
- `constraints.md`
- `change-inventory.md`
- `validation-pipeline.md`
- `operability.md`
- `security-boundary.md`
- `sync-policy.md`
- `progress.md`
- `decisions.md`
- `handoff.md`
- `completion.md`

## Round Rules

- Rebuild context from source files, logs, tests, and durable state.
- Read `.harness-run/docs/constraints.md`, `run-plan.md`, `project-architecture.md`, `validation-pipeline.md`, and `handoff.md` before editing.
- Establish or refresh the baseline before mutating anything.
- If verification is unclear, create or infer an execution checklist and evidence checklist before editing.
- Make one focused change or one falsifiable diagnosis.
- Verify mechanically when a command exists; otherwise verify by concrete evidence such as file inventory, diff review, build feasibility, sample output, screenshots, generated reports, or checklist completion.
- Keep, discard, block, or mark no-op.
- Record exactly one outcome before the next round.
- For partial goal-only rounds, use `refine`, `search`, or `pivot` with `metric=incomplete`; do not use `keep` until the metric is actually `complete`.
- Update `handoff.md` every round. Update at least one progress/evidence artifact each recorded round: `progress.md`, `decisions.md`, `change-inventory.md`, `run-plan.md`, `completion.md`, or `.harness-run/evidence/round-XXXX.md`.
- Keep raw logs and secrets out of Markdown docs; summarize only redacted facts.
- Never leave the next round dependent on hidden conversation state.

## Internal Control Plane

The skill keeps the heavier runtime protocol in `references/runtime-loop.md` and the helper script.

- `run-task` is the user entry. It creates or resumes the durable run and starts the background controller by default.
- `create-launch`, `launch`, `start`, `controller`, `init-state`, `record`, and `resume-prompt` are internal or advanced commands.
- The controller loop survives Codex context limits by relaunching fresh `codex exec` sessions from `.harness-run/`.
- `needs_human` means the controller stopped on a real blocker, inconsistent state, missing run artifacts, stale controller process, or stagnation, not that the user should keep waiting.

Typical flow:

1. Use `run-task`.
2. Check `status` if you need a progress summary.
3. Use `stop` when you want to end the run. For a prepared foreground run, `stop` clears the prepared state even when no background controller exists.
4. If a fresh Codex session must continue manually, use the internal `resume-prompt` command or read `.harness-run/state.json`.

Repeated starts:

- running `run-task` again with the same goal, scope, and verify command reuses the existing run
- running goal-only again with the same goal and scope reuses the existing plan/checklist run
- running it with a different behavior contract stops with `needs_human` instead of mixing state; contract comparison includes goal, scope, verify, metric, direction, guard, iterations, stop condition, execution policy, and codex args
- advanced fresh starts can pass `--force`, which archives existing `.harness-run` files before creating the new run
- `--force` refuses to archive while a background controller is still active; run `stop` first

## Multi-Agent Mode

- Delegate only independent side work.
- Use one agent for bounded source inspection, one for log or test verification, or one for review when those paths do not overlap.
- Do not duplicate the same investigation in multiple agents.
- Merge useful findings into durable state before the next round.

## Resume Discipline

- Resume from `.harness-run/state.json`, `.harness-run/rounds.tsv`, and `.harness-run/launch.json`, not from conversation memory.
- Re-read the state file, latest rounds, latest logs, `docs/handoff.md`, `docs/run-plan.md`, `docs/constraints.md`, and `docs/project-architecture.md` before changing anything.
- If evidence is missing, collect it first.
- If the harness state is inconsistent, stop as `needs_human` rather than inventing a recovery path.

## Boundary

`harness-run` makes runs resumable and can keep relaunching Codex while the Python controller and machine stay alive. It does not auto-restart after reboot, logout, or process termination. That is acceptable for this skill: after a reboot, manually start a fresh Codex session, read `.harness-run/state.json`, `.harness-run/rounds.tsv`, and `.harness-run/launch.json`, then continue with `run-task` using the same goal. It also does not prove semantic task completion by itself; completion still requires `run-plan.md`, `completion.md`, verification output, and evidence artifacts to support the final `complete` metric.

## References

- [references/runtime-loop.md](references/runtime-loop.md): launch contract, state files, round protocol, supervisor decisions, and prompt template
- [references/collaboration-protocol.md](references/collaboration-protocol.md): run-local collaboration discipline and update cadence
- [references/run-docs-protocol.md](references/run-docs-protocol.md): `.harness-run/docs/` file roles and sync boundaries
- [references/recovery-runbook.md](references/recovery-runbook.md): `needs_human`, stale runtime, and recovery rules
- [references/persistence-and-redaction.md](references/persistence-and-redaction.md): local-only files, redaction, and repo-sync safety
