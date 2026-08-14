# Harness Run Docs Protocol

This reference defines the run-local documentation generated under `.harness-run/docs/`.

## Required Run Docs

- `project-architecture.md`: evidence-backed architecture snapshot for this run.
- `product-context.md`: user, value, and tradeoff context.
- `run-plan.md`: goal, scope, milestones, verification, and plan change rules.
- `constraints.md`: user, repo, edit-boundary, validation, and safety constraints.
- `change-inventory.md`: allowed, touched, generated, ignored, and docs-sync paths.
- `validation-pipeline.md`: local and CI checks available to this run.
- `operability.md`: start, stop, resume, health, failure modes, and recovery.
- `security-boundary.md`: secret handling, redaction, shell, and persistence limits.
- `sync-policy.md`: what stays local and what should sync to target repo docs.
- `progress.md`: milestone-level status, not per-command logs.
- `decisions.md`: durable decisions and why they were made.
- `handoff.md`: the first file a fresh session should read.
- `completion.md`: final result and evidence.

## Optional Run Docs

- `ui-validation.md`: create/update when the task touches UI, browser, desktop, or visual behavior.
- `dependency-and-artifacts.md`: update when dependencies, toolchains, lockfiles, or build outputs change.
- `release-impact.md`: update when user-visible behavior changes.
- `design-index.md` and `design/*.md`: use when design or architecture notes need more room than `decisions.md`.
- `quality-notes.md`: update when the run changes or discovers quality waterline issues.
- `references.md`: record external sources and local examples.
- `generated-index.md` and `generated/*`: record generated knowledge snapshots and refresh commands.

## Target Repo Docs

If the target repo has its own docs system, `.harness-run/docs` remains the execution-layer record. Sync only concise summaries into target docs according to `sync-policy.md`.

If the target repo has no docs system, do not create one unless the user goal requires it.
