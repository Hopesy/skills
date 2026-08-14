#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ARTIFACT_DIR_NAME = ".harness-run"
CONTEXT_FILE_NAME = "context.json"
LAUNCH_FILE_NAME = "launch.json"
STATE_FILE_NAME = "state.json"
ROUNDS_FILE_NAME = "rounds.tsv"
RUNTIME_FILE_NAME = "runtime.json"
RUNTIME_LOG_FILE_NAME = "runtime.log"
POINTER_GIT_PATH = "harness-run/pointer.json"
DEFAULT_MANUAL_VERIFY = "manual evidence and completion checklist"
DEFAULT_MANUAL_METRIC = "planned work checklist"
DEFAULT_BACKGROUND_ITERATIONS = 25
DEFAULT_EXECUTION_POLICY = "workspace_write"
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUPS = 3
PASS_METRIC_VALUES = {"pass", "passed", "ok"}
COMPLETE_METRIC_VALUES = {"complete", "completed", "done"}
RUN_DOCS_DIR_NAME = "docs"
EVIDENCE_DIR_NAME = "evidence"
GENERATED_DIR_NAME = "generated"
DESIGN_DIR_NAME = "design"
RUN_DOC_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "references" / "templates"
RUN_DOC_TEMPLATES = {
    "project-architecture.md": "architecture_snapshot_path",
    "product-context.md": "product_context_path",
    "run-plan.md": "run_plan_path",
    "constraints.md": "constraints_path",
    "change-inventory.md": "change_inventory_path",
    "validation-pipeline.md": "validation_pipeline_path",
    "operability.md": "operability_path",
    "security-boundary.md": "security_boundary_path",
    "dependency-and-artifacts.md": "dependency_and_artifacts_path",
    "references.md": "references_path",
    "generated-index.md": "generated_index_path",
    "progress.md": "progress_path",
    "decisions.md": "decisions_path",
    "design-index.md": "design_index_path",
    "handoff.md": "handoff_path",
    "completion.md": "completion_path",
    "release-impact.md": "release_impact_path",
    "sync-policy.md": "sync_policy_path",
    "quality-notes.md": "quality_notes_path",
    "ui-validation.md": "ui_validation_path",
}
RUN_DOC_DIRECTORY_TEMPLATES = {
    "evidence/README.md": "evidence_readme_path",
    "generated/README.md": "generated_readme_path",
    "design/README.md": "design_readme_path",
}
VALID_DIRECTIONS = {"lower", "higher", "equal", "pass", "complete"}
VALID_STATUSES = {
    "keep",
    "discard",
    "crash",
    "no-op",
    "blocked",
    "refine",
    "pivot",
    "search",
    "drift",
}
CONTRACT_KEYS = (
    "goal",
    "scope",
    "metric",
    "direction",
    "verify",
    "verify_is_explicit",
    "guard",
    "iterations",
    "stop_condition",
    "execution_policy",
    "codex_args",
)


class HarnessRunError(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_now_precise() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))


def print_human_result(command: str, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        lines.append(summary.strip())
    else:
        lines.append(f"Harness run {command}: {payload.get('status', 'unknown')}")

    ordered_fields = [
        ("mode", "Mode"),
        ("goal", "Goal"),
        ("scope", "Scope"),
        ("verify", "Verify"),
        ("metric", "Metric"),
        ("current_metric", "Current metric"),
        ("round", "Round"),
        ("last_status", "Last status"),
        ("last_decision", "Last decision"),
        ("contract_mismatches", "Contract mismatches"),
        ("state_health", "State health"),
        ("state_warnings", "State warnings"),
        ("pid", "PID"),
        ("repo", "Repo"),
        ("workspace_root", "Workspace"),
        ("launch_path", "Launch"),
        ("runtime_path", "Runtime"),
        ("state_path", "State"),
        ("log_path", "Log"),
        ("run_docs_root", "Run docs"),
        ("run_plan_path", "Run plan"),
        ("architecture_snapshot_path", "Architecture"),
        ("constraints_path", "Constraints"),
        ("handoff_path", "Handoff"),
        ("evidence_root", "Evidence"),
        ("archived_paths", "Archived"),
        ("next_step", "Next step"),
    ]
    for key, label in ordered_fields:
        value = payload.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        lines.append(f"{label}: {value}")
    print("\n".join(lines))


def command_text(parts: list[object]) -> str:
    values = [str(part) for part in parts]
    if os.name == "nt":
        return subprocess.list2cmdline(values)
    return " ".join(shlex.quote(value) for value in values)


def tail_text(path: Path, *, max_lines: int = 10, max_chars: int = 4000) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    text = "\n".join(lines[-max_lines:])
    if len(text) > max_chars:
        text = text[-max_chars:]
    return text


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            Path(tmp_name).unlink()
        except FileNotFoundError:
            pass


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            if not content.endswith("\n"):
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            Path(tmp_name).unlink()
        except FileNotFoundError:
            pass


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise HarnessRunError(f"Missing JSON file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HarnessRunError(f"Invalid JSON file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise HarnessRunError(f"JSON root must be an object: {path}")
    return payload


def run_capture(command: list[str], *, cwd: Path | None = None) -> str | None:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def resolve_repo_path(raw: str | None) -> Path:
    candidate = Path(raw or os.getcwd()).expanduser().resolve()
    git_root = run_capture(["git", "-C", str(candidate), "rev-parse", "--show-toplevel"])
    if git_root:
        return Path(git_root).expanduser().resolve()
    return candidate


def resolve_workspace_root(repo: Path, raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()
    context = load_context_for_repo(repo)
    if context is not None:
        workspace = context.get("workspace_root")
        if isinstance(workspace, str) and workspace:
            return Path(workspace).expanduser().resolve()
    return repo


def artifact_paths(workspace_root: Path) -> dict[str, Path]:
    artifact_root = workspace_root / ARTIFACT_DIR_NAME
    run_docs_root = artifact_root / RUN_DOCS_DIR_NAME
    evidence_root = artifact_root / EVIDENCE_DIR_NAME
    generated_root = artifact_root / GENERATED_DIR_NAME
    design_root = artifact_root / DESIGN_DIR_NAME
    paths: dict[str, Path] = {
        "workspace_root": workspace_root,
        "artifact_root": artifact_root,
        "run_docs_root": run_docs_root,
        "evidence_root": evidence_root,
        "generated_root": generated_root,
        "design_root": design_root,
        "context_path": artifact_root / CONTEXT_FILE_NAME,
        "launch_path": artifact_root / LAUNCH_FILE_NAME,
        "state_path": artifact_root / STATE_FILE_NAME,
        "rounds_path": artifact_root / ROUNDS_FILE_NAME,
        "runtime_path": artifact_root / RUNTIME_FILE_NAME,
        "log_path": artifact_root / RUNTIME_LOG_FILE_NAME,
    }
    for filename, key in RUN_DOC_TEMPLATES.items():
        paths[key] = run_docs_root / filename
    for relative, key in RUN_DOC_DIRECTORY_TEMPLATES.items():
        paths[key] = artifact_root / relative
    return paths


def run_doc_path_payload(paths: dict[str, Path]) -> dict[str, str]:
    return {
        "run_docs_root": str(paths["run_docs_root"]),
        "evidence_root": str(paths["evidence_root"]),
        "generated_root": str(paths["generated_root"]),
        "design_root": str(paths["design_root"]),
        "architecture_snapshot_path": str(paths["architecture_snapshot_path"]),
        "product_context_path": str(paths["product_context_path"]),
        "run_plan_path": str(paths["run_plan_path"]),
        "constraints_path": str(paths["constraints_path"]),
        "change_inventory_path": str(paths["change_inventory_path"]),
        "validation_pipeline_path": str(paths["validation_pipeline_path"]),
        "operability_path": str(paths["operability_path"]),
        "security_boundary_path": str(paths["security_boundary_path"]),
        "dependency_and_artifacts_path": str(paths["dependency_and_artifacts_path"]),
        "references_path": str(paths["references_path"]),
        "generated_index_path": str(paths["generated_index_path"]),
        "progress_path": str(paths["progress_path"]),
        "decisions_path": str(paths["decisions_path"]),
        "design_index_path": str(paths["design_index_path"]),
        "handoff_path": str(paths["handoff_path"]),
        "completion_path": str(paths["completion_path"]),
        "release_impact_path": str(paths["release_impact_path"]),
        "sync_policy_path": str(paths["sync_policy_path"]),
        "quality_notes_path": str(paths["quality_notes_path"]),
        "ui_validation_path": str(paths["ui_validation_path"]),
    }


def git_pointer_path(repo: Path) -> Path | None:
    raw = run_capture(["git", "-C", str(repo), "rev-parse", "--git-path", POINTER_GIT_PATH])
    if not raw:
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = repo / candidate
    return candidate.expanduser().resolve()


def load_context_for_repo(repo: Path) -> dict[str, Any] | None:
    pointer_path = git_pointer_path(repo)
    if pointer_path is not None and pointer_path.exists():
        try:
            pointer = read_json(pointer_path)
            context_path = pointer.get("context_path")
            if isinstance(context_path, str) and context_path:
                candidate = Path(context_path).expanduser().resolve()
                if candidate.exists():
                    return read_json(candidate)
        except HarnessRunError:
            return None
    default_context = repo / ARTIFACT_DIR_NAME / CONTEXT_FILE_NAME
    if default_context.exists():
        try:
            return read_json(default_context)
        except HarnessRunError:
            return None
    return None


def resolve_paths(args: argparse.Namespace, *, require_context: bool = False) -> tuple[Path, dict[str, Path]]:
    repo = resolve_repo_path(getattr(args, "repo", None))
    workspace_root = resolve_workspace_root(repo, getattr(args, "workspace_root", None))
    paths = artifact_paths(workspace_root)
    if require_context and not paths["context_path"].exists():
        context = load_context_for_repo(repo)
        if context is None:
            raise HarnessRunError("No harness-run context found. Create or launch a run first.")
        workspace_root = Path(str(context["workspace_root"])).expanduser().resolve()
        paths = artifact_paths(workspace_root)
    return repo, paths


def format_markdown_list(items: list[str]) -> str:
    if not items:
        return "- none detected"
    return "\n".join(f"- `{item}`" for item in items)


def repo_relative(repo: Path, path: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return str(path)


def existing_repo_paths(repo: Path, candidates: list[str]) -> list[str]:
    found: list[str] = []
    for candidate in candidates:
        if (repo / candidate).exists():
            found.append(candidate)
    return found


def collect_repo_evidence(repo: Path) -> dict[str, list[str]]:
    root_candidates = [
        "AGENTS.md",
        "README.md",
        "CONTRIBUTING.md",
        "Makefile",
        "package.json",
        "pnpm-lock.yaml",
        "package-lock.json",
        "yarn.lock",
        "bun.lockb",
        "pyproject.toml",
        "requirements.txt",
        "uv.lock",
        "Cargo.toml",
        "Cargo.lock",
        "go.mod",
        "go.sum",
        "pom.xml",
        "build.gradle",
        "settings.gradle",
        "vite.config.ts",
        "vite.config.js",
        "next.config.js",
        "next.config.mjs",
        "tsconfig.json",
    ]
    doc_candidates = [
        "docs/ARCHITECTURE.md",
        "docs/PLANS_GUIDE.md",
        "docs/HISTORY_GUIDE.md",
        "docs/QUALITY_SCORE.md",
        "docs/RELIABILITY.md",
        "docs/SECURITY.md",
        "docs/CICD.md",
        "docs/FRONTEND.md",
        "docs/DESIGN.md",
        "docs/exec-plans",
        "docs/histories",
        "docs/releases",
    ]
    top_dirs = []
    for child in repo.iterdir() if repo.exists() else []:
        if child.is_dir() and child.name not in {".git", ARTIFACT_DIR_NAME, "node_modules", ".venv", "venv"}:
            top_dirs.append(child.name)
    return {
        "root_files": existing_repo_paths(repo, root_candidates),
        "docs": existing_repo_paths(repo, doc_candidates),
        "top_dirs": sorted(top_dirs)[:40],
    }


def render_run_doc_template(
    *,
    template_path: Path,
    manifest: dict[str, Any],
    repo: Path,
    paths: dict[str, Path],
) -> str:
    try:
        template = template_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        template = "# {{TITLE}}\n\nGenerated by harness-run.\n"
    config = manifest.get("config", {})
    evidence = collect_repo_evidence(repo)
    values = {
        "TITLE": template_path.stem.replace("-", " ").title(),
        "RUN_ID": str(manifest.get("run_id") or ""),
        "CREATED_AT": str(manifest.get("created_at") or utc_now()),
        "UPDATED_AT": utc_now(),
        "GOAL": str(config.get("goal") or ""),
        "ORIGINAL_GOAL": str(manifest.get("original_goal") or config.get("goal") or ""),
        "SCOPE": str(config.get("scope") or ""),
        "METRIC": str(config.get("metric") or ""),
        "DIRECTION": str(config.get("direction") or ""),
        "VERIFY": str(config.get("verify") or ""),
        "GUARD": str(config.get("guard") or "-"),
        "STOP_CONDITION": str(config.get("stop_condition") or ""),
        "SESSION_MODE": str(config.get("session_mode") or ""),
        "REPO": str(repo),
        "WORKSPACE_ROOT": str(paths["workspace_root"]),
        "ARTIFACT_ROOT": str(paths["artifact_root"]),
        "LAUNCH_PATH": str(paths["launch_path"]),
        "CONTEXT_PATH": str(paths["context_path"]),
        "STATE_PATH": str(paths["state_path"]),
        "ROUNDS_PATH": str(paths["rounds_path"]),
        "RUNTIME_PATH": str(paths["runtime_path"]),
        "RUNTIME_LOG_PATH": str(paths["log_path"]),
        "RUN_DOCS_ROOT": str(paths["run_docs_root"]),
        "EVIDENCE_ROOT": str(paths["evidence_root"]),
        "GENERATED_ROOT": str(paths["generated_root"]),
        "DESIGN_ROOT": str(paths["design_root"]),
        "ARCHITECTURE_SNAPSHOT_PATH": str(paths["architecture_snapshot_path"]),
        "RUN_PLAN_PATH": str(paths["run_plan_path"]),
        "CONSTRAINTS_PATH": str(paths["constraints_path"]),
        "HANDOFF_PATH": str(paths["handoff_path"]),
        "ROOT_EVIDENCE": format_markdown_list(evidence["root_files"]),
        "DOCS_EVIDENCE": format_markdown_list(evidence["docs"]),
        "TOP_DIRS": format_markdown_list(evidence["top_dirs"]),
    }
    def replace_token(match: re.Match[str]) -> str:
        token = match.group(1)
        return str(values.get(token, match.group(0)))

    rendered = re.sub(r"\{\{([A-Z0-9_]+)\}\}", replace_token, template)
    return rendered.rstrip() + "\n"


def ensure_run_docs(repo: Path, paths: dict[str, Path], manifest: dict[str, Any]) -> list[str]:
    created: list[str] = []
    paths["run_docs_root"].mkdir(parents=True, exist_ok=True)
    paths["evidence_root"].mkdir(parents=True, exist_ok=True)
    paths["generated_root"].mkdir(parents=True, exist_ok=True)
    paths["design_root"].mkdir(parents=True, exist_ok=True)
    for filename, key in RUN_DOC_TEMPLATES.items():
        target = paths[key]
        if target.exists():
            continue
        content = render_run_doc_template(
            template_path=RUN_DOC_TEMPLATE_DIR / filename,
            manifest=manifest,
            repo=repo,
            paths=paths,
        )
        write_text_atomic(target, content)
        created.append(str(target))
    for relative, key in RUN_DOC_DIRECTORY_TEMPLATES.items():
        target = paths[key]
        if target.exists():
            continue
        content = render_run_doc_template(
            template_path=RUN_DOC_TEMPLATE_DIR / relative.replace("/", "__"),
            manifest=manifest,
            repo=repo,
            paths=paths,
        )
        write_text_atomic(target, content)
        created.append(str(target))
    return created


def write_context_and_pointer(
    *,
    repo: Path,
    paths: dict[str, Path],
    active: bool,
    session_mode: str,
) -> None:
    context = {
        "version": 1,
        "active": active,
        "session_mode": session_mode,
        "workspace_root": str(paths["workspace_root"]),
        "artifact_root": str(paths["artifact_root"]),
        "primary_repo": str(repo),
        "launch_path": str(paths["launch_path"]),
        "state_path": str(paths["state_path"]),
        "rounds_path": str(paths["rounds_path"]),
        "runtime_path": str(paths["runtime_path"]),
        "log_path": str(paths["log_path"]),
        **run_doc_path_payload(paths),
        "updated_at": utc_now(),
    }
    write_json_atomic(paths["context_path"], context)
    pointer_path = git_pointer_path(repo)
    if pointer_path is None:
        return
    pointer = {
        "version": 1,
        "context_path": str(paths["context_path"]),
        "workspace_root": str(paths["workspace_root"]),
        "artifact_root": str(paths["artifact_root"]),
        "primary_repo": str(repo),
        "updated_at": utc_now(),
    }
    write_json_atomic(pointer_path, pointer)


def parse_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def metric_json(raw: object) -> dict[str, Any]:
    number = parse_number(raw)
    return {
        "raw": str(raw),
        "number": number,
    }


def metric_delta(current: object, previous: object) -> str:
    current_number = parse_number(current)
    previous_number = parse_number(previous)
    if current_number is None or previous_number is None:
        return ""
    delta = current_number - previous_number
    return f"{delta:g}"


def metric_improved(direction: str, current: object, previous: object) -> bool:
    current_number = parse_number(current)
    previous_number = parse_number(previous)
    if direction == "lower" and current_number is not None and previous_number is not None:
        return current_number < previous_number
    if direction == "higher" and current_number is not None and previous_number is not None:
        return current_number > previous_number
    if direction == "equal":
        return str(current).strip() == str(previous).strip()
    normalized = str(current).strip().lower()
    if direction == "pass":
        return normalized in PASS_METRIC_VALUES
    if direction == "complete":
        return normalized in COMPLETE_METRIC_VALUES
    return False


def append_round(paths: dict[str, Path], row: dict[str, Any]) -> None:
    rounds_path = paths["rounds_path"]
    rounds_path.parent.mkdir(parents=True, exist_ok=True)
    exists = rounds_path.exists()
    with rounds_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            delimiter="\t",
            fieldnames=["round", "time", "commit", "metric", "delta", "guard", "status", "description"],
            lineterminator="\n",
        )
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def latest_commit(repo: Path) -> str:
    commit = run_capture(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"])
    return commit or "-"


def build_launch_manifest(args: argparse.Namespace, repo: Path, paths: dict[str, Path]) -> dict[str, Any]:
    direction = args.direction.strip().lower()
    if direction not in VALID_DIRECTIONS:
        raise HarnessRunError(f"Unsupported direction: {args.direction}")
    return {
        "version": 1,
        "run_id": args.run_tag or f"harness-{int(time.time())}",
        "mode": args.mode,
        "created_at": utc_now(),
        "original_goal": args.original_goal or args.goal,
        "config": {
            "workspace_root": str(paths["workspace_root"]),
            "artifact_root": str(paths["artifact_root"]),
            "primary_repo": str(repo),
            "session_mode": getattr(args, "session_mode", "background"),
            "goal": args.goal,
            "scope": args.scope,
            "metric": args.metric,
            "direction": direction,
            "verify": args.verify,
            "verify_is_explicit": bool(getattr(args, "verify_is_explicit", True)),
            "guard": args.guard,
            "iterations": args.iterations,
            "stop_condition": args.stop_condition,
            "execution_policy": args.execution_policy,
            "codex_args": list(args.codex_arg or []),
        },
    }


def create_launch_manifest(args: argparse.Namespace) -> dict[str, Any]:
    repo, paths = resolve_paths(args)
    paths["artifact_root"].mkdir(parents=True, exist_ok=True)
    if paths["launch_path"].exists() and not args.force:
        raise HarnessRunError(f"{paths['launch_path']} already exists. Use --force to replace it.")
    manifest = build_launch_manifest(args, repo, paths)
    write_json_atomic(paths["launch_path"], manifest)
    created_docs = ensure_run_docs(repo, paths, manifest)
    write_context_and_pointer(
        repo=repo,
        paths=paths,
        active=True,
        session_mode=getattr(args, "session_mode", "background"),
    )
    return {
        "status": "created",
        "repo": str(repo),
        "workspace_root": str(paths["workspace_root"]),
        "launch_path": str(paths["launch_path"]),
        "context_path": str(paths["context_path"]),
        "run_docs_root": str(paths["run_docs_root"]),
        "run_plan_path": str(paths["run_plan_path"]),
        "handoff_path": str(paths["handoff_path"]),
        "created_docs": created_docs,
    }


def archive_run_artifacts(paths: dict[str, Path]) -> list[str]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    archived: list[str] = []
    for key in (
        "launch_path",
        "state_path",
        "rounds_path",
        "runtime_path",
        "log_path",
        "context_path",
        "run_docs_root",
        "evidence_root",
        "generated_root",
        "design_root",
    ):
        source = paths[key]
        if not source.exists():
            continue
        target = source.with_name(f"{source.name}.prev-{timestamp}")
        counter = 1
        while target.exists():
            target = source.with_name(f"{source.name}.prev-{timestamp}-{counter}")
            counter += 1
        if source.is_dir():
            shutil.move(str(source), str(target))
        else:
            source.replace(target)
        archived.append(str(target))
    return archived


def load_launch(paths: dict[str, Path]) -> dict[str, Any]:
    return read_json(paths["launch_path"])


def load_state(paths: dict[str, Path]) -> dict[str, Any] | None:
    if not paths["state_path"].exists():
        return None
    return read_json(paths["state_path"])


def build_initial_state(manifest: dict[str, Any], metric_value: str, commit: str, description: str) -> dict[str, Any]:
    metric = metric_json(metric_value)
    return {
        "version": 1,
        "run_id": manifest["run_id"],
        "mode": manifest.get("mode", "loop"),
        "config": dict(manifest["config"]),
        "state": {
            "round": 0,
            "baseline_metric": metric,
            "current_metric": metric,
            "best_metric": metric,
            "best_round": 0,
            "last_commit": commit,
            "last_trial_commit": commit,
            "last_trial_metric": metric,
            "last_status": "baseline",
            "keeps": 0,
            "discards": 0,
            "crashes": 0,
            "no_ops": 0,
            "blocked": 0,
            "pivots": 0,
            "description": description,
        },
        "supervisor": {
            "recommended_action": "relaunch",
            "restart_count": 0,
            "stagnation_count": 0,
            "last_observed_signature": "",
        },
        "updated_at": utc_now(),
    }


def init_state(args: argparse.Namespace) -> dict[str, Any]:
    repo, paths = resolve_paths(args, require_context=True)
    manifest = load_launch(paths)
    if paths["state_path"].exists() and not args.force:
        raise HarnessRunError(f"{paths['state_path']} already exists. Use --force to replace it.")
    commit = args.commit or latest_commit(repo)
    description = args.description or "baseline"
    state = build_initial_state(manifest, args.metric_value, commit, description)
    if paths["rounds_path"].exists() and args.force:
        paths["rounds_path"].unlink()
    append_round(
        paths,
        {
            "round": 0,
            "time": utc_now(),
            "commit": commit,
            "metric": args.metric_value,
            "delta": "0",
            "guard": args.guard or "-",
            "status": "baseline",
            "description": description,
        },
    )
    write_json_atomic(paths["state_path"], state)
    write_context_and_pointer(
        repo=repo,
        paths=paths,
        active=True,
        session_mode=str(manifest.get("config", {}).get("session_mode") or "background"),
    )
    return {
        "status": "initialized",
        "round": 0,
        "state_path": str(paths["state_path"]),
        "rounds_path": str(paths["rounds_path"]),
    }


def update_counters(snapshot: dict[str, Any], status: str) -> None:
    if status == "keep":
        snapshot["keeps"] = int(snapshot.get("keeps", 0)) + 1
    elif status == "discard":
        snapshot["discards"] = int(snapshot.get("discards", 0)) + 1
    elif status == "crash":
        snapshot["crashes"] = int(snapshot.get("crashes", 0)) + 1
    elif status == "no-op":
        snapshot["no_ops"] = int(snapshot.get("no_ops", 0)) + 1
    elif status == "blocked":
        snapshot["blocked"] = int(snapshot.get("blocked", 0)) + 1
    elif status == "pivot":
        snapshot["pivots"] = int(snapshot.get("pivots", 0)) + 1


def record_round(args: argparse.Namespace) -> dict[str, Any]:
    repo, paths = resolve_paths(args, require_context=True)
    state = load_state(paths)
    if state is None:
        raise HarnessRunError("State is missing. Run init-state after measuring the baseline.")
    status = args.status.strip()
    if status not in VALID_STATUSES:
        raise HarnessRunError(f"Unsupported status: {status}")
    config = state["config"]
    snapshot = dict(state["state"])
    current_metric = snapshot["current_metric"]["raw"]
    trial_metric = args.metric_value if args.metric_value is not None else current_metric
    if status == "keep" and not metric_improved(str(config["direction"]), trial_metric, current_metric):
        raise HarnessRunError("Status keep requires an improved metric for the configured direction.")
    next_round = int(snapshot.get("round", 0)) + 1
    commit = args.commit or latest_commit(repo)
    append_round(
        paths,
        {
            "round": next_round,
            "time": utc_now(),
            "commit": commit,
            "metric": trial_metric,
            "delta": metric_delta(trial_metric, current_metric),
            "guard": args.guard or "-",
            "status": status,
            "description": args.description,
        },
    )
    trial_metric_payload = metric_json(trial_metric)
    snapshot["round"] = next_round
    snapshot["last_trial_commit"] = commit
    snapshot["last_trial_metric"] = trial_metric_payload
    snapshot["last_status"] = status
    snapshot["description"] = args.description
    if status in {"keep", "drift"}:
        snapshot["current_metric"] = trial_metric_payload
        snapshot["last_commit"] = commit
        if metric_improved(str(config["direction"]), trial_metric, snapshot["best_metric"]["raw"]):
            snapshot["best_metric"] = trial_metric_payload
            snapshot["best_round"] = next_round
    update_counters(snapshot, status)
    state["state"] = snapshot
    state["updated_at"] = utc_now()
    write_json_atomic(paths["state_path"], state)
    return {
        "status": status,
        "round": next_round,
        "state_path": str(paths["state_path"]),
        "rounds_path": str(paths["rounds_path"]),
        "retained_metric": snapshot["current_metric"],
    }


def process_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    if os.name == "nt":
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        if completed.returncode != 0:
            return False
        for row in csv.reader(completed.stdout.splitlines()):
            if len(row) > 1 and row[1].strip() == str(pid):
                return True
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except ProcessLookupError:
        return False
    return True


def load_runtime(paths: dict[str, Path]) -> dict[str, Any] | None:
    if not paths["runtime_path"].exists():
        return None
    return read_json(paths["runtime_path"])


def persist_runtime(paths: dict[str, Path], payload: dict[str, Any]) -> None:
    payload["updated_at"] = utc_now()
    write_json_atomic(paths["runtime_path"], payload)


def persist_prepared_runtime(paths: dict[str, Path], *, session_mode: str) -> None:
    runtime = {
        "version": 1,
        "pid": None,
        "status": "prepared",
        "session_mode": session_mode,
        "last_decision": "prepare",
        "terminal_reason": "none",
    }
    runtime.update(run_doc_path_payload(paths))
    persist_runtime(paths, runtime)


def runtime_is_running(paths: dict[str, Path]) -> bool:
    runtime = load_runtime(paths)
    if runtime is None:
        return False
    pid = runtime.get("pid")
    return isinstance(pid, int) and process_alive(pid) and runtime.get("status") == "running"


def archive_path(path: Path) -> str | None:
    if not path.exists():
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    target = path.with_name(f"{path.name}.prev-{timestamp}")
    counter = 1
    while target.exists():
        target = path.with_name(f"{path.name}.prev-{timestamp}-{counter}")
        counter += 1
    if path.is_dir():
        shutil.move(str(path), str(target))
    else:
        path.replace(target)
    return str(target)


def rotate_log(path: Path, *, max_bytes: int = LOG_MAX_BYTES, backups: int = LOG_BACKUPS) -> list[str]:
    if not path.exists() or path.stat().st_size <= max_bytes:
        return []
    archived: list[str] = []
    for index in range(backups, 0, -1):
        source = path.with_name(f"{path.name}.{index}")
        target = path.with_name(f"{path.name}.{index + 1}")
        if not source.exists():
            continue
        if index == backups:
            source.unlink()
            continue
        source.replace(target)
    first_backup = path.with_name(f"{path.name}.1")
    path.replace(first_backup)
    archived.append(str(first_backup))
    return archived


def codex_policy_args(execution_policy: str, extra_args: list[str]) -> list[str]:
    args = list(extra_args)
    if execution_policy == "danger_full_access":
        bypass = "--dangerously-bypass-approvals-and-sandbox"
        if bypass not in args:
            args.insert(0, bypass)
    return args


def build_codex_command(codex_bin: str, manifest: dict[str, Any], repo: Path) -> list[str]:
    config = manifest["config"]
    extra_args = [str(value) for value in config.get("codex_args", [])]
    policy_args = codex_policy_args(str(config.get("execution_policy") or DEFAULT_EXECUTION_POLICY), extra_args)
    return [codex_bin, "exec", *policy_args, "-C", str(repo), "-"]


def file_signature(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    stat = path.stat()
    return {"path": str(path), "mtime_ns": stat.st_mtime_ns, "size": stat.st_size}


def newest_file_signature(root: Path) -> dict[str, Any] | None:
    if not root.exists():
        return None
    newest: Path | None = None
    newest_mtime = -1
    for child in root.rglob("*"):
        if not child.is_file():
            continue
        mtime = child.stat().st_mtime_ns
        if mtime > newest_mtime:
            newest = child
            newest_mtime = mtime
    return file_signature(newest) if newest is not None else None


def artifact_signature(paths: dict[str, Path]) -> dict[str, Any]:
    keys = [
        "run_plan_path",
        "handoff_path",
        "progress_path",
        "decisions_path",
        "change_inventory_path",
        "completion_path",
    ]
    return {
        "docs": {key: file_signature(paths[key]) for key in keys},
        "latest_evidence": newest_file_signature(paths["evidence_root"]),
    }


def progress_signature(state: dict[str, Any], paths: dict[str, Path] | None = None) -> str:
    snapshot = state.get("state", {})
    payload = {
        "current_metric": snapshot.get("current_metric"),
        "best_metric": snapshot.get("best_metric"),
        "last_commit": snapshot.get("last_commit"),
        "last_trial_commit": snapshot.get("last_trial_commit"),
    }
    if paths is not None:
        payload["artifacts"] = artifact_signature(paths)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def stop_condition_satisfied(config: dict[str, Any], metric: object) -> bool:
    condition = str(config.get("stop_condition") or "").strip().lower()
    if not condition:
        return False
    metric_number = parse_number(metric)
    if metric_number is not None:
        match = re.search(r"(<=|>=|==|=|<|>)\s*(-?\d+(?:\.\d+)?)", condition)
        if match:
            operator, raw_target = match.groups()
            target = float(raw_target)
            if operator in {"=", "=="}:
                return metric_number == target
            if operator == "<=":
                return metric_number <= target
            if operator == ">=":
                return metric_number >= target
            if operator == "<":
                return metric_number < target
            if operator == ">":
                return metric_number > target
        if config.get("direction") == "lower" and "zero" in condition:
            return metric_number == 0
    text = str(metric).strip().lower()
    if config.get("direction") == "pass":
        return text in PASS_METRIC_VALUES
    if config.get("direction") == "complete":
        return text in COMPLETE_METRIC_VALUES
    return False


def path_modified_after(path: Path, instant: datetime) -> bool:
    if not path.exists():
        return False
    modified_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    return modified_at > instant


def any_path_modified_after(paths_to_check: list[Path], instant: datetime) -> bool:
    return any(path_modified_after(path, instant) for path in paths_to_check)


def newest_file_modified_after(root: Path, instant: datetime) -> bool:
    if not root.exists():
        return False
    for child in root.rglob("*"):
        if child.is_file() and path_modified_after(child, instant):
            return True
    return False


def validate_round_artifacts(
    *,
    paths: dict[str, Path],
    state: dict[str, Any],
    round_started_at: object,
) -> list[str]:
    started_at = parse_utc(round_started_at)
    if started_at is None:
        return ["runtime round_started_at is missing or invalid"]
    snapshot = state.get("state", {})
    try:
        round_number = int(snapshot.get("round", 0))
    except (TypeError, ValueError):
        return ["state round is missing or invalid"]
    if round_number <= 0:
        return []
    errors: list[str] = []
    if not path_modified_after(paths["handoff_path"], started_at):
        errors.append("handoff.md was not updated during the recorded round")
    activity_paths = [
        paths["run_plan_path"],
        paths["progress_path"],
        paths["decisions_path"],
        paths["change_inventory_path"],
        paths["completion_path"],
    ]
    if not any_path_modified_after(activity_paths, started_at) and not newest_file_modified_after(paths["evidence_root"], started_at):
        errors.append("no progress, decision, plan, completion, change-inventory, or evidence artifact changed during the recorded round")
    current_metric = snapshot.get("current_metric", {})
    current_metric_raw = current_metric.get("raw") if isinstance(current_metric, dict) else current_metric
    if str(current_metric_raw).strip().lower() in COMPLETE_METRIC_VALUES and not path_modified_after(
        paths["completion_path"],
        started_at,
    ):
        errors.append("completion.md was not updated during the round that marked the run complete")
    return errors


def evaluate_supervisor(
    *,
    paths: dict[str, Path],
    after_run: bool,
    max_stagnation: int,
) -> dict[str, Any]:
    state = load_state(paths)
    if state is None:
        return {
            "decision": "relaunch",
            "reason": "missing_state",
            "reasons": ["Nested Codex has not initialized .harness-run/state.json yet."],
            "state_written": False,
        }
    snapshot = state.get("state", {})
    config = state.get("config", {})
    reasons: list[str] = []
    decision = "relaunch"
    reason = "none"
    if snapshot.get("last_status") == "blocked":
        decision = "needs_human"
        reason = "blocked"
        reasons.append("Last recorded round is blocked.")
    elif isinstance(config.get("iterations"), int) and int(snapshot.get("round", 0)) >= int(config["iterations"]):
        decision = "stop"
        reason = "iteration_cap_reached"
        reasons.append("Configured iteration cap reached.")
    elif stop_condition_satisfied(config, snapshot.get("current_metric", {}).get("raw")):
        decision = "stop"
        reason = "goal_reached"
        reasons.append("Configured stop condition is satisfied.")
    else:
        reasons.append("Run remains resumable.")

    supervisor = dict(state.get("supervisor") or {})
    signature = progress_signature(state, paths)
    same_signature = supervisor.get("last_observed_signature") == signature
    restart_count = int(supervisor.get("restart_count", 0)) + (1 if after_run else 0)
    stagnation_count = int(supervisor.get("stagnation_count", 0))
    previous_round = supervisor.get("last_observed_round")
    round_advanced = after_run and snapshot.get("round") != previous_round
    if decision in {"relaunch", "stop"} and round_advanced:
        runtime = load_runtime(paths) or {}
        artifact_errors = validate_round_artifacts(
            paths=paths,
            state=state,
            round_started_at=runtime.get("round_started_at"),
        )
        if artifact_errors:
            decision = "needs_human"
            reason = "missing_round_artifacts"
            reasons.extend(artifact_errors)
    if after_run:
        stagnation_count = stagnation_count + 1 if same_signature else 0
    if decision == "relaunch" and stagnation_count >= max_stagnation:
        decision = "needs_human"
        reason = "stagnated"
        reasons.append(f"No progress signature change across {stagnation_count} supervised exits.")

    state["supervisor"] = {
        "recommended_action": decision,
        "should_continue": decision == "relaunch",
        "terminal_reason": "none" if decision == "relaunch" else reason,
        "last_exit_kind": "turn_complete" if decision == "relaunch" else reason,
        "last_observed_signature": signature,
        "last_observed_round": snapshot.get("round"),
        "last_observed_status": snapshot.get("last_status"),
        "restart_count": restart_count,
        "stagnation_count": stagnation_count,
        "updated_at": utc_now(),
    }
    write_json_atomic(paths["state_path"], state)
    return {
        "decision": decision,
        "reason": reason,
        "reasons": reasons,
        "round": snapshot.get("round"),
        "last_status": snapshot.get("last_status"),
        "restart_count": restart_count,
        "stagnation_count": stagnation_count,
        "state_written": True,
    }


def build_runtime_prompt(
    *,
    script_path: Path,
    repo: Path,
    paths: dict[str, Path],
    manifest: dict[str, Any],
) -> str:
    state = load_state(paths)
    config = manifest["config"]
    init_command = command_text(
        [
            "python",
            script_path,
            "init-state",
            "--repo",
            repo,
            "--metric-value",
            "<baseline>",
            "--commit",
            "<commit>",
            "--description",
            "baseline",
        ]
    )
    record_command = command_text(
        [
            "python",
            script_path,
            "record",
            "--repo",
            repo,
            "--status",
            "refine|search|pivot|keep|discard|crash|no-op|blocked|drift",
            "--metric-value",
            "<metric>",
            "--commit",
            "<commit>",
            "--guard",
            "pass|fail|-",
            "--description",
            "<summary>",
        ]
    )
    lines = [
        "$harness-run",
        "This repo is managed by the harness-run runtime controller.",
        "The launch contract is already confirmed. Do not ask for launch confirmation.",
        "",
        f"Goal: {config.get('goal')}",
        f"Scope: {config.get('scope')}",
        f"Metric: {config.get('metric')}",
        f"Direction: {config.get('direction')}",
        f"Verify: {config.get('verify')}",
        f"Guard: {config.get('guard') or '-'}",
        f"Stop condition: {config.get('stop_condition') or '-'}",
        "",
        f"Repo: {repo}",
        f"Launch: {paths['launch_path']}",
        f"State: {paths['state_path']}",
        f"Rounds: {paths['rounds_path']}",
        f"Run plan: {paths['run_plan_path']}",
        f"Architecture snapshot: {paths['architecture_snapshot_path']}",
        f"Constraints: {paths['constraints_path']}",
        f"Handoff: {paths['handoff_path']}",
        f"Evidence: {paths['evidence_root']}",
        "",
        "Required protocol:",
        "1. Rebuild context from source, AGENTS.md, logs/tests, launch.json, state.json, rounds.tsv, and .harness-run/docs.",
        "2. Read constraints.md, run-plan.md, project-architecture.md, validation-pipeline.md, and handoff.md before editing.",
        "3. Refresh project-architecture.md only when source evidence changes; never replace it with guesses.",
        "4. Keep .harness-run/docs as the run-level collaboration record. Do not put raw secrets, tokens, or full runtime logs into docs.",
    ]
    if config.get("verify_is_explicit", True):
        lines.extend(
            [
                "5. If state.json does not exist, run the verify command to measure the baseline before editing.",
                "6. After baseline, initialize state with:",
            ]
        )
        next_step_number = 7
    else:
        lines.extend(
            [
                "5. No explicit verify command was provided. Derive or update the execution plan and evidence checklist in run-plan.md from the user's goal, project docs, source, and existing plans.",
                "6. If the user named a plan directory or plan file, follow it as authoritative scope and sequence; do not renegotiate it.",
                "7. If state.json does not exist, initialize the baseline as incomplete after reading enough project evidence.",
                "8. Initialize state with:",
            ]
        )
        next_step_number = 9
    lines.extend(
        [
            f"   {init_command}",
            f"{next_step_number}. Make one focused change or one falsifiable diagnosis.",
            f"{next_step_number + 1}. Run Verify and Guard when configured. When Verify is manual, collect concrete review evidence instead.",
            f"{next_step_number + 2}. Write concise evidence to .harness-run/evidence/round-XXXX.md when this round produces new evidence.",
            f"{next_step_number + 3}. Update handoff.md every round; update progress.md, decisions.md, change-inventory.md, and sync-policy.md only when their facts change.",
            f"{next_step_number + 4}. Record exactly one outcome before exiting this turn:",
            f"   {record_command}",
            f"{next_step_number + 5}. For partial goal-only rounds, use status=refine/search/pivot with metric=incomplete. Do not use status=keep with metric=incomplete.",
            f"{next_step_number + 6}. Use status=keep with metric=complete only when run-plan.md and completion evidence are fully satisfied.",
            f"{next_step_number + 7}. A round that records state but does not update handoff.md and at least one progress/evidence artifact will be stopped as needs_human.",
            f"{next_step_number + 8}. Do not leave progress only in the conversation.",
            f"{next_step_number + 9}. Continue autonomously until a terminal condition, iteration cap, or blocker is reached.",
        ]
    )
    if state is None:
        lines.extend(["", "Current state: missing. Start with baseline measurement and init-state."])
    else:
        snapshot = state.get("state", {})
        lines.extend(
            [
                "",
                "Current state:",
                f"- round: {snapshot.get('round')}",
                f"- current_metric: {snapshot.get('current_metric')}",
                f"- best_metric: {snapshot.get('best_metric')}",
                f"- last_status: {snapshot.get('last_status')}",
                f"- description: {snapshot.get('description')}",
            ]
        )
    rounds_tail = tail_text(paths["rounds_path"])
    if rounds_tail:
        lines.extend(["", "Latest rounds.tsv entries:", "```tsv", rounds_tail, "```"])
    return "\n".join(lines).strip() + "\n"


def start_runtime(args: argparse.Namespace, *, runner_path: Path) -> dict[str, Any]:
    repo, paths = resolve_paths(args, require_context=True)
    if runtime_is_running(paths):
        raise HarnessRunError("A harness-run runtime is already running for this workspace.")
    if not paths["launch_path"].exists():
        raise HarnessRunError(f"Missing launch manifest: {paths['launch_path']}")
    launch_manifest = load_launch(paths)
    session_mode = str(launch_manifest.get("config", {}).get("session_mode") or "background")
    codex_bin = args.codex_bin or "codex"
    if shutil.which(codex_bin) is None:
        raise HarnessRunError(f"Codex executable is not available: {codex_bin}")
    paths["artifact_root"].mkdir(parents=True, exist_ok=True)
    rotated_logs = rotate_log(paths["log_path"])
    log_handle = paths["log_path"].open("a", encoding="utf-8")
    command = [
        sys.executable,
        str(runner_path),
        "controller",
        "--repo",
        str(repo),
        "--workspace-root",
        str(paths["workspace_root"]),
        "--sleep-seconds",
        str(args.sleep_seconds),
        "--max-stagnation",
        str(args.max_stagnation),
        "--codex-bin",
        codex_bin,
    ]
    popen_kwargs: dict[str, Any] = {
        "cwd": str(paths["workspace_root"]),
        "stdin": subprocess.DEVNULL,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
        "text": True,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **popen_kwargs)
    log_handle.close()
    runtime = {
        "version": 1,
        "status": "running",
        "pid": process.pid,
        "command": command,
        "repo": str(repo),
        "workspace_root": str(paths["workspace_root"]),
        "launch_path": str(paths["launch_path"]),
        "state_path": str(paths["state_path"]),
        "rounds_path": str(paths["rounds_path"]),
        "log_path": str(paths["log_path"]),
        **run_doc_path_payload(paths),
        "started_at": utc_now(),
        "last_decision": "running",
        "terminal_reason": "none",
        "rotated_logs": rotated_logs,
    }
    persist_runtime(paths, runtime)
    write_context_and_pointer(repo=repo, paths=paths, active=True, session_mode=session_mode)
    return {
        "status": "running",
        "pid": process.pid,
        "runtime_path": str(paths["runtime_path"]),
        "log_path": str(paths["log_path"]),
    }


def launch_and_start(args: argparse.Namespace, *, runner_path: Path) -> dict[str, Any]:
    created = create_launch_manifest(args)
    started = start_runtime(args, runner_path=runner_path)
    return {**created, **started}


def mark_needs_human(paths: dict[str, Path], runtime: dict[str, Any], reason: str, error: str | None = None) -> int:
    runtime["status"] = "needs_human"
    runtime["last_decision"] = "needs_human"
    runtime["terminal_reason"] = reason
    runtime["last_error"] = error
    persist_runtime(paths, runtime)
    return 2


def run_runtime(args: argparse.Namespace, *, runner_path: Path) -> int:
    repo, paths = resolve_paths(args, require_context=True)
    manifest = load_launch(paths)
    runtime = load_runtime(paths) or {
        "version": 1,
        "status": "running",
        "pid": os.getpid(),
        "repo": str(repo),
        "workspace_root": str(paths["workspace_root"]),
        "started_at": utc_now(),
    }
    runtime["pid"] = os.getpid()
    runtime["status"] = "running"
    persist_runtime(paths, runtime)
    startup_failures = 0
    codex_bin = args.codex_bin or "codex"
    if shutil.which(codex_bin) is None:
        return mark_needs_human(paths, runtime, "codex_unavailable", f"Codex executable is not available: {codex_bin}")

    while True:
        runtime = load_runtime(paths) or runtime
        if runtime.get("stop_requested_at"):
            runtime["status"] = "stopped"
            runtime["last_decision"] = "stop"
            runtime["terminal_reason"] = "user_stopped"
            persist_runtime(paths, runtime)
            write_context_and_pointer(
                repo=repo,
                paths=paths,
                active=False,
                session_mode=str(manifest.get("config", {}).get("session_mode") or "background"),
            )
            return 0
        prompt = build_runtime_prompt(script_path=runner_path, repo=repo, paths=paths, manifest=manifest)
        command = build_codex_command(codex_bin, manifest, repo)
        env = dict(os.environ)
        env["HARNESS_RUN_ACTIVE"] = "1"
        env["HARNESS_RUN_CONTEXT"] = str(paths["context_path"])
        env["HARNESS_RUN_STATE"] = str(paths["state_path"])
        env["HARNESS_RUN_RUNTIME"] = str(paths["runtime_path"])
        runtime["round_started_at"] = utc_now_precise()
        persist_runtime(paths, runtime)
        try:
            codex_exit = subprocess.run(
                command,
                cwd=str(paths["workspace_root"]),
                input=prompt,
                text=True,
                encoding="utf-8",
                env=env,
            ).returncode
        except OSError as exc:
            return mark_needs_human(paths, runtime, "codex_launch_failed", str(exc))

        supervisor = evaluate_supervisor(paths=paths, after_run=True, max_stagnation=args.max_stagnation)
        decision = supervisor["decision"]
        reason = supervisor["reason"]
        if reason == "missing_state":
            startup_failures += 1
            if codex_exit == 0:
                decision = "needs_human"
                reason = "missing_state_after_success"
            elif startup_failures >= args.max_stagnation:
                decision = "needs_human"
                reason = "startup_failed_before_state"
        else:
            startup_failures = 0

        runtime["last_codex_exit"] = codex_exit
        runtime["last_decision"] = decision
        runtime["last_reason"] = reason
        runtime["last_supervisor"] = supervisor
        if decision == "relaunch":
            runtime["status"] = "running"
            runtime["terminal_reason"] = "none"
            persist_runtime(paths, runtime)
            time.sleep(args.sleep_seconds)
            continue
        runtime["status"] = "terminal" if decision == "stop" else "needs_human"
        runtime["terminal_reason"] = reason
        persist_runtime(paths, runtime)
        write_context_and_pointer(
            repo=repo,
            paths=paths,
            active=False,
            session_mode=str(manifest.get("config", {}).get("session_mode") or "background"),
        )
        return 0 if decision == "stop" else 2


def runtime_status(args: argparse.Namespace) -> dict[str, Any]:
    repo, paths = resolve_paths(args)
    runtime = load_runtime(paths)
    state = load_state(paths)
    launch = load_launch(paths) if paths["launch_path"].exists() else {}
    config = (state or launch).get("config", {}) if isinstance((state or launch), dict) else {}
    snapshot = state.get("state", {}) if state is not None else {}
    current_metric = snapshot.get("current_metric")
    current_metric_raw = (
        current_metric.get("raw")
        if isinstance(current_metric, dict)
        else current_metric
    )
    explicit_verify = bool(config.get("verify_is_explicit", True))
    prepared_next_step = (
        "Measure the baseline, run init-state, then record each round."
        if explicit_verify
        else "Derive the execution plan/checklist, initialize baseline as incomplete, then record each round."
    )
    if runtime is None:
        if launch:
            if str(config.get("session_mode") or "background") == "foreground":
                status = "prepared"
                summary = "Harness run is prepared for foreground execution in the current Codex session."
                next_step = prepared_next_step
            elif state is not None:
                status = "idle"
                summary = "Harness run has saved state but no active background controller."
                next_step = "Use run-task with the same goal and verify command to continue, or inspect the saved state."
            else:
                status = "prepared"
                summary = "Harness run is configured but has not started yet."
                next_step = "Use run-task with the same goal and verify command to launch it."
        else:
            status = "idle"
            summary = "Harness run is not active."
            next_step = "Use run-task to create a new durable run."
        if state is not None and stop_condition_satisfied(config, current_metric_raw):
            status = "terminal"
            summary = "Harness run reached a terminal stop: goal_reached."
            next_step = "Inspect the final state or launch a new run if more work is needed."
        has_artifacts = bool(launch or state is not None)
        payload = {
            "status": status,
            "summary": summary,
            "next_step": next_step,
            "mode": config.get("session_mode"),
            "repo": str(repo),
            "workspace_root": str(paths["workspace_root"]),
            "goal": config.get("goal"),
            "scope": config.get("scope"),
            "verify": config.get("verify"),
            "metric": config.get("metric"),
            "launch_path": str(paths["launch_path"]) if launch else None,
            "context_path": str(paths["context_path"]) if has_artifacts else None,
            "runtime_path": str(paths["runtime_path"]) if has_artifacts else None,
            "log_path": str(paths["log_path"]) if has_artifacts else None,
            "state_path": str(paths["state_path"]) if has_artifacts else None,
            "has_state": state is not None,
            "current_metric": current_metric_raw,
        }
        if has_artifacts:
            payload.update(run_doc_path_payload(paths))
        return payload
    pid = runtime.get("pid")
    alive = isinstance(pid, int) and process_alive(pid)
    status = runtime.get("status", "unknown")
    if status == "running" and not alive:
        runtime["status"] = "crashed"
        runtime["last_decision"] = "needs_human"
        runtime["terminal_reason"] = "controller_pid_dead"
        runtime["crashed_at"] = utc_now()
        persist_runtime(paths, runtime)
        status = "crashed"
    goal_reached = state is not None and stop_condition_satisfied(config, current_metric_raw)
    terminal_reason = runtime.get("terminal_reason")
    if status in {"idle", "prepared"} and goal_reached:
        status = "terminal"
        if terminal_reason in (None, "", "none"):
            terminal_reason = "goal_reached"
    if status == "needs_human":
        summary = f"Harness run needs human attention: {runtime.get('terminal_reason') or runtime.get('last_reason') or 'unknown'}."
        next_step = "Read runtime.log, state.json, and the latest rounds.tsv entries before continuing."
    elif status == "terminal":
        summary = f"Harness run reached a terminal stop: {terminal_reason or 'completed'}."
        next_step = "Inspect the final state or launch a new run if more work is needed."
    elif status == "stopped":
        summary = "Harness run has stopped."
        next_step = "Use run-task with the same goal and verify command to continue, or run-task --force for a fresh run."
    elif status == "crashed":
        summary = "Harness run controller is not alive but runtime.json still existed."
        next_step = "Read runtime.log, state.json, rounds.tsv, and handoff.md before continuing or restarting."
    elif status == "prepared":
        summary = "Harness run is prepared for foreground execution in the current Codex session."
        next_step = prepared_next_step
    elif status == "running":
        summary = "Harness run is running."
        next_step = "Use status to monitor progress or stop to end the run."
    else:
        summary = f"Harness run is {status}."
        next_step = "Inspect the durable state before continuing."
    payload = {
        "status": status,
        "summary": summary,
        "next_step": next_step,
        "mode": config.get("session_mode"),
        "repo": str(repo),
        "workspace_root": str(paths["workspace_root"]),
        "goal": config.get("goal"),
        "scope": config.get("scope"),
        "verify": config.get("verify"),
        "metric": config.get("metric"),
        "pid": pid,
        "alive": alive,
        "launch_path": str(paths["launch_path"]) if launch else None,
        "context_path": str(paths["context_path"]),
        "runtime_path": str(paths["runtime_path"]),
        "log_path": str(paths["log_path"]),
        "state_path": str(paths["state_path"]),
        "last_decision": runtime.get("last_decision"),
        "terminal_reason": terminal_reason,
        "round": snapshot.get("round"),
        "last_status": snapshot.get("last_status"),
        "current_metric": current_metric_raw,
    }
    payload.update(run_doc_path_payload(paths))
    return payload


def terminate_process_tree(pid: int, grace_seconds: float) -> None:
    if not process_alive(pid):
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T"], capture_output=True, text=True)
        deadline = time.time() + max(grace_seconds, 0)
        while time.time() < deadline and process_alive(pid):
            time.sleep(0.1)
        if process_alive(pid):
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        os.kill(pid, signal.SIGTERM)
    deadline = time.time() + max(grace_seconds, 0)
    while time.time() < deadline and process_alive(pid):
        time.sleep(0.1)
    if process_alive(pid):
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except OSError:
            os.kill(pid, signal.SIGKILL)


def check_state_consistency(paths: dict[str, Path]) -> list[str]:
    warnings: list[str] = []
    state_round: int | None = None
    if paths["state_path"].exists():
        try:
            state = read_json(paths["state_path"])
            snapshot = state.get("state", {})
            raw_round = snapshot.get("round")
            if isinstance(raw_round, int):
                state_round = raw_round
            else:
                warnings.append("state.json does not contain an integer state.round")
        except HarnessRunError as exc:
            warnings.append(str(exc))
    if paths["rounds_path"].exists():
        try:
            with paths["rounds_path"].open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
        except OSError as exc:
            warnings.append(f"Cannot read rounds.tsv: {exc}")
            rows = []
        if rows:
            try:
                rounds_round = int(rows[-1].get("round") or "")
            except ValueError:
                warnings.append("rounds.tsv last row does not contain an integer round")
            else:
                if state_round is not None and rounds_round != state_round:
                    warnings.append(f"state.json round {state_round} does not match rounds.tsv last round {rounds_round}")
    return warnings


def stop_runtime(args: argparse.Namespace) -> dict[str, Any]:
    repo, paths = resolve_paths(args)
    runtime = load_runtime(paths)
    if runtime is None:
        launch = load_launch(paths) if paths["launch_path"].exists() else {}
        config = launch.get("config", {}) if isinstance(launch, dict) else {}
        if launch:
            session_mode = str(config.get("session_mode") or "background")
            persist_runtime(
                paths,
                {
                    "version": 1,
                    "pid": None,
                    "status": "stopped",
                    "session_mode": session_mode,
                    "last_decision": "stop",
                    "terminal_reason": "user_stopped",
                    "stop_requested_at": utc_now(),
                    **run_doc_path_payload(paths),
                },
            )
            write_context_and_pointer(repo=repo, paths=paths, active=False, session_mode=session_mode)
            return {
                "status": "stopped",
                "summary": "Harness run stopped.",
                "repo": str(repo),
                "workspace_root": str(paths["workspace_root"]),
                "launch_path": str(paths["launch_path"]),
                "runtime_path": str(paths["runtime_path"]),
                "handoff_path": str(paths["handoff_path"]),
            }
        return {
            "status": "idle",
            "summary": "Harness run is not active.",
            "repo": str(repo),
            "workspace_root": str(paths["workspace_root"]),
            "runtime_path": None,
        }
    runtime["stop_requested_at"] = utc_now()
    persist_runtime(paths, runtime)
    pid = runtime.get("pid")
    if isinstance(pid, int) and process_alive(pid):
        terminate_process_tree(pid, args.grace_seconds)
    state_warnings = check_state_consistency(paths)
    runtime["status"] = "stopped"
    runtime["last_decision"] = "stop"
    runtime["terminal_reason"] = "user_stopped"
    runtime["state_health"] = "warning" if state_warnings else "ok"
    runtime["state_warnings"] = state_warnings
    persist_runtime(paths, runtime)
    launch_manifest = load_launch(paths) if paths["launch_path"].exists() else {}
    write_context_and_pointer(
        repo=repo,
        paths=paths,
        active=False,
        session_mode=str(launch_manifest.get("config", {}).get("session_mode") or "background"),
    )
    return {
        "status": "stopped",
        "summary": "Harness run stopped.",
        "pid": pid,
        "repo": str(repo),
        "workspace_root": str(paths["workspace_root"]),
        "launch_path": str(paths["launch_path"]) if paths["launch_path"].exists() else None,
        "runtime_path": str(paths["runtime_path"]),
        "handoff_path": str(paths["handoff_path"]),
        "state_health": "warning" if state_warnings else "ok",
        "state_warnings": state_warnings,
    }


def resume_prompt(args: argparse.Namespace) -> dict[str, Any]:
    repo, paths = resolve_paths(args, require_context=True)
    manifest = load_launch(paths)
    prompt = build_runtime_prompt(script_path=Path(__file__).resolve(), repo=repo, paths=paths, manifest=manifest)
    print(prompt, end="")
    return {"status": "printed", "launch_path": str(paths["launch_path"])}


def launch_contract_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "goal": args.goal,
        "scope": args.scope,
        "metric": args.metric,
        "direction": args.direction,
        "verify": args.verify,
        "verify_is_explicit": bool(args.verify_is_explicit),
        "guard": args.guard,
        "iterations": args.iterations,
        "stop_condition": args.stop_condition,
        "execution_policy": args.execution_policy,
        "codex_args": list(args.codex_arg or []),
    }


def contract_mismatches(existing_config: dict[str, Any], requested_config: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    for key in CONTRACT_KEYS:
        if existing_config.get(key) != requested_config.get(key):
            mismatches.append(key)
    return mismatches


def run_task(args: argparse.Namespace, *, runner_path: Path) -> dict[str, Any]:
    if args.foreground and args.background:
        raise HarnessRunError("--foreground and --background cannot both be set.")
    repo = resolve_repo_path(args.repo)
    args.repo = str(repo)
    args.workspace_root = args.workspace_root or str(repo)
    args.original_goal = args.original_goal or args.goal
    args.mode = "loop"
    args.session_mode = "foreground" if args.foreground else "background"
    args.execution_policy = args.execution_policy or DEFAULT_EXECUTION_POLICY
    args.codex_arg = args.codex_arg or []
    args.verify_is_explicit = bool(args.verify)
    if not args.verify:
        args.verify = DEFAULT_MANUAL_VERIFY
        if args.metric == "verification result":
            args.metric = DEFAULT_MANUAL_METRIC
        if not args.direction:
            args.direction = "complete"
    elif not args.direction:
        args.direction = "pass"
    if args.metric == "verification result":
        args.metric = args.verify
    if not args.stop_condition:
        if args.direction == "pass":
            args.stop_condition = "pass"
        elif args.direction == "complete":
            args.stop_condition = "complete"
    if args.iterations is None and args.session_mode == "background":
        args.iterations = DEFAULT_BACKGROUND_ITERATIONS
    _, paths = resolve_paths(args)
    archived_paths: list[str] = []
    if paths["launch_path"].exists() and args.force and runtime_is_running(paths):
        return {
            "status": "needs_human",
            "summary": "A background harness run is still active; force-start refused.",
            "mode": "background",
            "repo": str(repo),
            "runtime_path": str(paths["runtime_path"]),
            "launch_path": str(paths["launch_path"]),
            "run_plan_path": str(paths["run_plan_path"]),
            "handoff_path": str(paths["handoff_path"]),
            "next_step": "Run stop first, then rerun run-task --force if you want a fresh run.",
        }
    if paths["launch_path"].exists() and not args.force:
        existing = load_launch(paths)
        created_docs = ensure_run_docs(repo, paths, existing)
        existing_config = existing.get("config", {}) if isinstance(existing, dict) else {}
        requested_config = launch_contract_from_args(args)
        write_context_and_pointer(
            repo=repo,
            paths=paths,
            active=True,
            session_mode=str(existing_config.get("session_mode") or args.session_mode),
        )
        mismatches = contract_mismatches(existing_config, requested_config)
        if mismatches:
            return {
                "status": "needs_human",
                "summary": "A different harness run already exists for this workspace.",
                "mode": existing_config.get("session_mode"),
                "goal": existing_config.get("goal"),
                "scope": existing_config.get("scope"),
                "verify": existing_config.get("verify"),
                "contract_mismatches": mismatches,
                "repo": str(repo),
                "launch_path": str(paths["launch_path"]),
                "run_plan_path": str(paths["run_plan_path"]),
                "handoff_path": str(paths["handoff_path"]),
                "next_step": "Stop or finish the existing run, or rerun with --force to archive it and start fresh.",
            }
        if runtime_is_running(paths):
            return runtime_status(args)
        if args.session_mode == "foreground":
            archived_runtime = []
            existing_runtime = load_runtime(paths)
            if existing_runtime is not None and existing_runtime.get("status") != "prepared":
                archived = archive_path(paths["runtime_path"])
                if archived:
                    archived_runtime.append(archived)
            persist_prepared_runtime(paths, session_mode="foreground")
            write_context_and_pointer(repo=repo, paths=paths, active=True, session_mode="foreground")
            next_step = (
                "Measure the baseline if needed, then record each round."
                if args.verify_is_explicit
                else "Derive the execution plan/checklist, initialize baseline as incomplete, then record each round."
            )
            payload = {
                "status": "prepared",
                "summary": "Existing foreground harness run is ready in this workspace.",
                "mode": "foreground",
                "repo": str(repo),
                "workspace_root": str(paths["workspace_root"]),
                "launch_path": str(paths["launch_path"]),
                "context_path": str(paths["context_path"]),
                "run_docs_root": str(paths["run_docs_root"]),
                "run_plan_path": str(paths["run_plan_path"]),
                "handoff_path": str(paths["handoff_path"]),
                "created_docs": created_docs,
                "next_step": next_step,
            }
            if archived_runtime:
                payload["archived_paths"] = archived_runtime
            return payload
        started = start_runtime(args, runner_path=runner_path)
        return {
            "status": "running",
            "summary": "Existing background harness run started.",
            "mode": "background",
            "repo": str(repo),
            "workspace_root": str(paths["workspace_root"]),
            "launch_path": str(paths["launch_path"]),
            "runtime_path": started["runtime_path"],
            "log_path": started["log_path"],
            "run_docs_root": str(paths["run_docs_root"]),
            "run_plan_path": str(paths["run_plan_path"]),
            "handoff_path": str(paths["handoff_path"]),
            "created_docs": created_docs,
            "pid": started["pid"],
            "next_step": "Use status to inspect progress or stop to end the run.",
        }
    if paths["launch_path"].exists() and args.force:
        archived_paths = archive_run_artifacts(paths)

    if args.session_mode == "foreground":
        created = create_launch_manifest(args)
        persist_prepared_runtime(paths, session_mode="foreground")
        next_step = (
            "Measure the baseline, run init-state, then record each round."
            if args.verify_is_explicit
            else "Derive the execution plan/checklist, initialize baseline as incomplete, then record each round."
        )
        payload = {
            "status": "prepared",
            "summary": "Foreground harness run prepared. Continue in the current Codex session.",
            "mode": "foreground",
            "repo": created["repo"],
            "workspace_root": created["workspace_root"],
            "launch_path": created["launch_path"],
            "context_path": created["context_path"],
            "run_docs_root": created["run_docs_root"],
            "run_plan_path": created["run_plan_path"],
            "handoff_path": created["handoff_path"],
            "created_docs": created["created_docs"],
            "next_step": next_step,
        }
        if archived_paths:
            payload["archived_paths"] = archived_paths
        return payload

    launched = launch_and_start(args, runner_path=runner_path)
    payload = {
        "status": "running",
        "summary": "Background harness run launched.",
        "mode": "background",
        "repo": launched["repo"],
        "workspace_root": launched["workspace_root"],
        "launch_path": launched["launch_path"],
        "runtime_path": launched["runtime_path"],
        "log_path": launched["log_path"],
        "run_docs_root": str(paths["run_docs_root"]),
        "run_plan_path": str(paths["run_plan_path"]),
        "handoff_path": str(paths["handoff_path"]),
        "created_docs": launched.get("created_docs", []),
        "pid": launched["pid"],
        "next_step": "Use status to inspect progress or stop to end the run.",
    }
    if archived_paths:
        payload["archived_paths"] = archived_paths
    return payload


def add_manifest_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--original-goal")
    parser.add_argument("--mode", default="loop")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--metric", required=True)
    parser.add_argument("--direction", required=True, choices=sorted(VALID_DIRECTIONS))
    parser.add_argument("--verify", required=True)
    parser.add_argument("--guard")
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--stop-condition")
    parser.add_argument("--run-tag")
    parser.add_argument("--session-mode", choices=["foreground", "background"], default="background")
    parser.add_argument(
        "--execution-policy",
        choices=["danger_full_access", "workspace_write"],
        default=DEFAULT_EXECUTION_POLICY,
    )
    parser.add_argument("--codex-arg", action="append", default=[])
    parser.add_argument("--force", action="store_true")


def add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", default=".")
    parser.add_argument("--workspace-root")
    parser.add_argument("--sleep-seconds", type=int, default=5)
    parser.add_argument("--max-stagnation", type=int, default=3)
    parser.add_argument("--codex-bin", default="codex")


def add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Control harness-run durable Codex loops.")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="{run-task,status,stop}")

    run_task_parser = subparsers.add_parser(
        "run-task",
        help="Start or continue a durable harness run.",
    )
    add_json_flag(run_task_parser)
    run_task_parser.add_argument("--repo", default=".", help="Repository or workspace path. Default: current directory.")
    run_task_parser.add_argument("--workspace-root", help=argparse.SUPPRESS)
    run_task_parser.add_argument("--original-goal", help=argparse.SUPPRESS)
    run_task_parser.add_argument("--goal", required=True, help="What the run should accomplish.")
    run_task_parser.add_argument("--verify", help="Optional mechanical verification command.")
    run_task_parser.add_argument("--scope", default=".", help="In-scope files, modules, or directories.")
    run_task_parser.add_argument("--metric", default="verification result", help=argparse.SUPPRESS)
    run_task_parser.add_argument(
        "--direction",
        choices=sorted(VALID_DIRECTIONS),
        default=None,
        help=argparse.SUPPRESS,
    )
    run_task_parser.add_argument("--guard", help=argparse.SUPPRESS)
    run_task_parser.add_argument("--iterations", type=int, help=argparse.SUPPRESS)
    run_task_parser.add_argument("--stop-condition", help=argparse.SUPPRESS)
    run_task_parser.add_argument("--run-tag", help=argparse.SUPPRESS)
    run_task_parser.add_argument("--foreground", action="store_true", help="Prepare the run for the current session instead of launching the background controller.")
    run_task_parser.add_argument("--background", action="store_true", help=argparse.SUPPRESS)
    run_task_parser.add_argument(
        "--execution-policy",
        choices=["danger_full_access", "workspace_write"],
        default=DEFAULT_EXECUTION_POLICY,
        help=argparse.SUPPRESS,
    )
    run_task_parser.add_argument("--codex-arg", action="append", default=[], help=argparse.SUPPRESS)
    run_task_parser.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    run_task_parser.add_argument("--sleep-seconds", type=int, default=5, help=argparse.SUPPRESS)
    run_task_parser.add_argument("--max-stagnation", type=int, default=3, help=argparse.SUPPRESS)
    run_task_parser.add_argument("--codex-bin", default="codex", help=argparse.SUPPRESS)

    create = subparsers.add_parser("create-launch", help="Write .harness-run/launch.json and context.")
    add_manifest_args(create)

    launch = subparsers.add_parser("launch", help="Create a launch manifest and start the detached controller.")
    add_manifest_args(launch)
    launch.add_argument("--sleep-seconds", type=int, default=5)
    launch.add_argument("--max-stagnation", type=int, default=3)
    launch.add_argument("--codex-bin", default="codex")

    start = subparsers.add_parser("start", help="Start the detached controller from an existing launch manifest.")
    add_runtime_args(start)

    controller = subparsers.add_parser("controller", help="Internal controller loop.")
    add_runtime_args(controller)

    status = subparsers.add_parser("status", help="Show current run status.")
    add_json_flag(status)
    status.add_argument("--repo", default=".", help="Repository or workspace path. Default: current directory.")
    status.add_argument("--workspace-root", help=argparse.SUPPRESS)

    stop = subparsers.add_parser("stop", help="Stop the current run.")
    add_json_flag(stop)
    stop.add_argument("--repo", default=".", help="Repository or workspace path. Default: current directory.")
    stop.add_argument("--workspace-root", help=argparse.SUPPRESS)
    stop.add_argument("--grace-seconds", type=float, default=5.0, help=argparse.SUPPRESS)

    init = subparsers.add_parser("init-state", help="Initialize state after measuring the baseline.")
    init.add_argument("--repo", required=True)
    init.add_argument("--workspace-root")
    init.add_argument("--metric-value", required=True)
    init.add_argument("--commit")
    init.add_argument("--guard")
    init.add_argument("--description")
    init.add_argument("--force", action="store_true")

    record = subparsers.add_parser("record", help="Append one round and update state.")
    record.add_argument("--repo", required=True)
    record.add_argument("--workspace-root")
    record.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    record.add_argument("--metric-value")
    record.add_argument("--commit")
    record.add_argument("--guard")
    record.add_argument("--description", required=True)

    prompt = subparsers.add_parser("resume-prompt", help="Print the runtime prompt for the next Codex session.")
    prompt.add_argument("--repo", default=".")
    prompt.add_argument("--workspace-root")
    subparsers._choices_actions = [
        action
        for action in subparsers._choices_actions
        if action.dest in {"run-task", "status", "stop"}
    ]
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    runner_path = Path(__file__).resolve()
    if args.command == "run-task":
        payload = run_task(args, runner_path=runner_path)
        print_json(payload) if args.json else print_human_result(args.command, payload)
        return 0
    if args.command == "create-launch":
        print_json(create_launch_manifest(args))
        return 0
    if args.command == "launch":
        print_json(launch_and_start(args, runner_path=runner_path))
        return 0
    if args.command == "start":
        print_json(start_runtime(args, runner_path=runner_path))
        return 0
    if args.command == "controller":
        return run_runtime(args, runner_path=runner_path)
    if args.command == "status":
        payload = runtime_status(args)
        print_json(payload) if args.json else print_human_result(args.command, payload)
        return 0
    if args.command == "stop":
        payload = stop_runtime(args)
        print_json(payload) if args.json else print_human_result(args.command, payload)
        return 0
    if args.command == "init-state":
        print_json(init_state(args))
        return 0
    if args.command == "record":
        print_json(record_round(args))
        return 0
    if args.command == "resume-prompt":
        resume_prompt(args)
        return 0
    raise HarnessRunError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HarnessRunError as exc:
        raise SystemExit(f"error: {exc}")
