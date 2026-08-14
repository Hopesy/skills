# Harness Run Runtime Loop

Use this reference when a task needs Codex to keep working from durable state across fresh contexts or background relaunches.

## Launch Contract

Only `Goal` must come from the user. Infer the rest from the user's request and repo evidence before starting:

- `Goal`: what should be improved, fixed, or verified
- `Scope`: files, modules, packages, or repos in scope
- `Metric`: the mechanical signal that proves progress
- `Direction`: lower, higher, equal, pass/fail, or checklist complete
- `Verify`: command, test, log inspection, or other concrete check

Recommended optional fields:

- `Guard`: regression check that must stay green
- `Iterations`: explicit cap; otherwise continue until the stop condition
- `Stop condition`: success, hard blocker, budget exhausted, or user interruption
- `Run mode`: foreground or background
- `Execution policy`: defaults to `workspace_write`; use `danger_full_access` only when the user explicitly accepts the elevated background risk

If a missing field can be inferred safely, infer it. If verification is unclear, launch anyway with `metric=planned work checklist`, `direction=complete`, and `stop_condition=complete`. Background goal-only runs use a default iteration cap of 25 unless the user gives a different cap. The first round must derive an execution plan and evidence checklist from project docs, source, tests, logs, and any user-named plan files. Ask only when continuing would likely produce work opposite to the user's intent.

If the user explicitly says to follow a directory, plan file, roadmap, issue list, checklist, or existing project plan, treat that plan as authoritative scope and sequence. Read it, follow it, and do not renegotiate it unless it contradicts safety, repo instructions, or executable evidence.

## Control Plane

All normal run artifacts live under:

```text
<workspace_root>/.harness-run/
```

Files:

- `launch.json`: immutable-ish launch manifest confirmed by the starting session
- `state.json`: primary recovery snapshot
- `rounds.tsv`: append-only audit trail
- `runtime.json`: background controller pid/status/last decision
- `runtime.log`: background controller and nested Codex output
- `context.json`: canonical path map for this run
- `docs/`: run-local collaboration record
- `evidence/`: concise per-round evidence notes
- `generated/`: generated knowledge snapshots
- `design/`: detailed design notes when needed

Each managed git repo may also get a git-local pointer at:

```bash
git rev-parse --git-path harness-run/pointer.json
```

That pointer references the workspace-owned `.harness-run/context.json`.

Run docs are initialized from `references/templates/`. The controller and nested sessions must treat them as the human-readable run record:

- `project-architecture.md`: evidence-backed architecture snapshot
- `run-plan.md`: active plan, scope, milestones, verification, and stop condition
- `constraints.md`: user constraints, repo instructions, edit boundaries, validation, and safety rules
- `validation-pipeline.md`: available local and CI verification paths
- `progress.md`: milestone-level status
- `decisions.md`: key decisions and rationale
- `handoff.md`: first read for a fresh session; update every round
- `completion.md`: final result and verification record
- `sync-policy.md`: what stays local and what may sync into target repo docs

Use the high-level helper for normal starts:

```bash
python <skill-root>/scripts/harness_run_ctl.py run-task --goal "<goal>"
python <skill-root>/scripts/harness_run_ctl.py run-task --goal "<goal>" --verify "<command>"
python <skill-root>/scripts/harness_run_ctl.py status
python <skill-root>/scripts/harness_run_ctl.py stop
```

Advanced/internal commands:

```bash
python <skill-root>/scripts/harness_run_ctl.py create-launch --repo <repo> --workspace-root <workspace> --goal "<goal>" --scope "<scope>" --metric "<metric>" --direction lower --verify "<command>"
python <skill-root>/scripts/harness_run_ctl.py launch --repo <repo> --workspace-root <workspace> --goal "<goal>" --scope "<scope>" --metric "<metric>" --direction lower --verify "<command>"
python <skill-root>/scripts/harness_run_ctl.py start
python <skill-root>/scripts/harness_run_ctl.py controller
python <skill-root>/scripts/harness_run_ctl.py init-state --repo <repo> --metric-value <number-or-text> --commit <hash> --description "<baseline>"
python <skill-root>/scripts/harness_run_ctl.py record --repo <repo> --status refine --metric-value incomplete --commit <hash> --guard pass --description "<what changed>"
python <skill-root>/scripts/harness_run_ctl.py resume-prompt
```

## Round Contract

Each round must end with one of these outcomes:

- A verified code or documentation change
- A verified diagnosis with the next implementation step
- A real blocker with exact evidence

Round algorithm:

1. Rebuild context from source files, logs, tests, and durable state.
2. Read `docs/constraints.md`, `docs/run-plan.md`, `docs/project-architecture.md`, `docs/validation-pipeline.md`, and `docs/handoff.md`.
3. Choose one focused change or one falsifiable diagnosis.
4. Apply the change or collect the evidence.
5. Run `Verify` when it is explicit; otherwise collect concrete evidence against the inferred plan/checklist.
6. Run `Guard` when configured.
7. Use `refine`, `search`, or `pivot` for partial goal-only work; reserve `keep` for an improved metric or final `complete`.
8. Discard or revert the result if it worsened the metric or broke the guard.
9. Update `handoff.md` every round; update at least one progress/evidence artifact such as progress, decisions, inventory, run plan, completion, or `.harness-run/evidence/round-XXXX.md`.
10. Log the result in durable state before the next round.

For goal-only runs, initialize the baseline as `incomplete`, use non-terminal statuses such as `refine`, `search`, `pivot`, or `blocked` for partial rounds, and record `status=keep --metric-value complete` only when the plan is fully satisfied with evidence.

Do not leave the next round dependent on hidden conversation state.

## Background Relaunch

`harness_run_ctl.py launch` writes `launch.json`, writes `context.json`, writes the git-local pointer when possible, and starts a detached controller process.

The controller loop:

1. checks whether a stop was requested;
2. verifies `launch.json`, `state.json`, and `runtime.json` are coherent enough to continue;
3. builds a compact runtime prompt from the manifest and state;
4. runs `codex exec -C <repo> -` with the prompt on stdin;
5. evaluates the supervisor state after Codex exits, including stale controller detection, artifact freshness, stop conditions, iteration caps, and stagnation;
6. relaunches, stops, or marks `needs_human`.

This design continues across Codex context limits because every nested session is disposable. It does not auto-restart after machine shutdown. Manual continuation after reboot is expected: start a fresh Codex session, read `.harness-run/launch.json`, `.harness-run/state.json`, `.harness-run/rounds.tsv`, and `.harness-run/runtime.log`, then continue with the same `run-task` contract.

## Supervisor Decisions

The controller should continue only when state says the loop remains resumable.

- `relaunch`: goal not reached, not blocked, iteration cap not reached, and progress signature has not stagnated past the configured threshold.
- `stop`: stop condition reached, iteration cap reached, or a one-shot run completed.
- `needs_human`: state is inconsistent, required run artifacts were not updated, verify artifacts are missing repeatedly, the last round is `blocked`, stop failed, Codex cannot launch, the controller pid is stale, or the run stagnated across too many supervised exits.

Never convert `needs_human` into another unattended relaunch.

## Multi-Agent Split

Use subagents only when their work can proceed independently of the main critical path:

- Explorer: read a bounded code path and report entry points, invariants, and risks
- Verifier: run or inspect tests, logs, snapshots, and command output
- Reviewer: inspect the final diff for regressions and missing coverage

Keep implementation ownership clear. Do not ask multiple agents to edit the same files unless there is an explicit merge plan.

Merge every useful subagent result into durable state before ending the round.

## Docs Sync

`.harness-run/docs` is always the run-local execution record. If the target repo has its own `docs/` structure, sync only concise, redacted summaries when `docs/sync-policy.md` says to sync. Do not create a full target-repo docs system unless the user goal requires it.

Keep raw `runtime.log` local. Summarize facts into Markdown after redaction.

## Compact Prompt Template

```text
Use $harness-run.

Goal:
<user goal>

Persist progress in:
<workspace_root>/.harness-run/state.json

Persist collaboration notes in:
<workspace_root>/.harness-run/docs/

Launch contract:
- Scope:
- Metric:
- Direction:
- Verify:
- Guard:
- Run mode:
- Execution policy:

Run bounded rounds:
1. Rebuild context from source files, logs, tests, and the state file.
2. Read constraints, run-plan, architecture snapshot, validation pipeline, and handoff from `.harness-run/docs/`.
3. Establish or refresh the baseline with the verify command when Verify is explicit.
4. Derive an execution plan and evidence checklist, then initialize baseline as incomplete when Verify is not explicit.
5. Choose the smallest useful next slice.
6. Implement or diagnose that slice.
7. Verify with concrete commands, logs, or evidence against the plan/checklist.
8. Update handoff every round and update at least one progress/evidence artifact.
9. Use refine/search/pivot for partial goal-only rounds; use keep only for improved or complete metrics.
10. Record with scripts/harness_run_ctl.py.
11. Continue only from persisted state.
```
