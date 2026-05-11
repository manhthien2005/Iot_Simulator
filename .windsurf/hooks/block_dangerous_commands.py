#!/usr/bin/env python3
"""
Block dangerous commands before Cascade executes them.

Listens on `pre_run_command` hook. Exits with code 2 to block, 0 to allow.

Project-scoped — only blocks the most destructive patterns. The user can still
manually run any command in their own terminal; this only guards Cascade's
auto-execution path.

If Python is not installed, the hook command fails with a non-zero exit code
that is neither 0 nor 2, so Cascade treats it as a hook error and lets the
action proceed normally (graceful degradation — does not break the workflow).

Categories:
1. HARD_BLOCK — catastrophic patterns, never auto-runnable
2. CONFIRMED_PATTERNS — needs explicit `# CONFIRMED-<TOKEN>` in command
3. TRUNK_BRANCH_GUARD — block git commit/push when on trunk branch
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# ---- Trunks per repo (per ADR-003: HealthGuard = develop) -----------------
TRUNK_BRANCHES = frozenset({"main", "master", "develop", "deploy", "production", "prod", "release"})

# ---- Patterns that are ALWAYS blocked (no override) -----------------------
HARD_BLOCK_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+-[rRf]+\s+/(?:\s|$)", "rm -rf / (recursive root delete)"),
    (r"\brm\s+-[rRf]+\s+\*\s*$", "rm -rf * (recursive cwd wipe)"),
    (r"\brm\s+-[rRf]+\s+~\s*$", "rm -rf ~ (home directory wipe)"),
    (r"\bmkfs\.", "mkfs (filesystem format)"),
    (r"\bdd\s+if=.*of=/dev/[sh]d", "dd to raw disk device"),
    (r"\bformat\s+[a-zA-Z]:", "Windows format <drive>:"),
    (r"\bdel\s+/[fFsSqQ]+\s+/[fFsSqQ]+", "del /F /S /Q (recursive force delete)"),
    (r"\brmdir\s+/[sSqQ]+", "rmdir /S (recursive directory delete)"),
    (r"\bRemove-Item\s+(?:.*\s)?-Recurse\s+(?:.*\s)?-Force\b", "PowerShell Remove-Item -Recurse -Force"),
    (r":\(\)\s*\{.*:\|:.*\}\s*;\s*:", "fork bomb"),
    # Database destructive (no override — too dangerous)
    (
        r"\b(?:psql|mysql|mongo|sqlite3?)\b.*(?:\bDROP\s+(?:DATABASE|SCHEMA|TABLE)\b|\bTRUNCATE\b)",
        "DB DROP/TRUNCATE via CLI",
    ),
    (
        r"\bnpx\s+prisma\s+migrate\s+reset\b",
        "Prisma migrate reset (drops + recreates DB)",
    ),
    (
        r"\bdocker\s+(?:compose\s+)?down\s+(?:.*\s)?-v\b",
        "docker-compose down -v (deletes volumes — destroys DB data)",
    ),
    (
        r"\bdocker\s+(?:compose\s+)?down\s+(?:.*\s)?--volumes\b",
        "docker-compose down --volumes (deletes volumes)",
    ),
]

# ---- Patterns that require explicit user confirmation in the command ------
CONFIRMED_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"\bgit\s+push\s+(?:.*\s)?(?:-f|--force|--force-with-lease)\b",
        "git push --force",
        "Add `# CONFIRMED-FORCE-PUSH` to the command, OR use --force-with-lease on a feature branch.",
    ),
    (
        r"\bfirebase\s+(?:deploy|firestore:delete|database:remove)\b.*--project[= ](?:.*?)(?:prod|production)",
        "firebase destructive op against prod project",
        "Add `# CONFIRMED-PROD-DEPLOY` to the command after a manual review.",
    ),
    (
        r"\bgcloud\s+(?:.*\s)?(?:projects\s+delete|sql\s+databases\s+delete|storage\s+rm\s+-r)",
        "gcloud destructive operation",
        "Add `# CONFIRMED-GCLOUD-DESTRUCTIVE` to the command line.",
    ),
    (
        r"\bnpm\s+(?:publish|unpublish)\b",
        "npm publish/unpublish",
        "Add `# CONFIRMED-NPM-PUBLISH` if intentional.",
    ),
    (
        r"\bpub\s+publish\b",
        "dart pub publish",
        "Add `# CONFIRMED-PUB-PUBLISH` if intentional.",
    ),
    (
        r"\bgit\s+reset\s+(?:.*\s)?--hard\b",
        "git reset --hard (destructive — drops uncommitted work)",
        "Add `# CONFIRMED-RESET-HARD` if you really want to discard local changes.",
    ),
    (
        r"\bflutter\s+clean\b",
        "flutter clean (forbidden auto-run per personal-operating-mode rule)",
        "Add `# CONFIRMED-FLUTTER-CLEAN` if you intentionally want to wipe build cache.",
    ),
    (
        r"\bgit\s+clean\s+-[fdx]+",
        "git clean -fdx (deletes untracked files including ignored)",
        "Add `# CONFIRMED-GIT-CLEAN` if intentional.",
    ),
    (
        r"\b(?:npm\s+(?:install|i)|yarn\s+add|pnpm\s+(?:add|install))\s+(?:-[^\s]*\s+)*[a-zA-Z@][^\s]*",
        "npm/yarn/pnpm install <package> (adds new dependency — discuss first)",
        "Add `# CONFIRMED-ADD-DEP` after deciding on the package + version with the user.",
    ),
    (
        r"\b(?:flutter\s+pub\s+add|dart\s+pub\s+add)\s+[a-zA-Z][^\s]*",
        "flutter/dart pub add <package> (adds new dependency — discuss first)",
        "Add `# CONFIRMED-ADD-DEP` after deciding on the package + version with the user.",
    ),
    (
        r"\bfirebase\s+auth:(?:export|import)\b",
        "firebase auth:export/import (PII bulk read/write)",
        "Add `# CONFIRMED-AUTH-PII` after manual security review.",
    ),
    (
        r"\bnpx\s+prisma\s+(?:db\s+push|migrate\s+deploy)\b",
        "Prisma db push / migrate deploy (production schema change)",
        "Add `# CONFIRMED-PRISMA-DEPLOY` after backup verified.",
    ),
]

CONFIRM_TOKEN_RE = re.compile(
    r"#\s*CONFIRMED-(?:FORCE-PUSH|PROD-DEPLOY|GCLOUD-DESTRUCTIVE|NPM-PUBLISH|PUB-PUBLISH"
    r"|RESET-HARD|FLUTTER-CLEAN|GIT-CLEAN|ADD-DEP|AUTH-PII|PRISMA-DEPLOY|TRUNK-COMMIT|TRUNK-PUSH)\b"
)


def get_current_branch(cwd: str | None) -> str | None:
    """Return current git branch in cwd, or None if not in repo / git fails."""
    if not cwd:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return branch if branch else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def check_trunk_guard(cmd: str, cwd: str | None) -> tuple[str, str] | None:
    """If command is git commit/push and current branch is trunk, return (label, hint)."""
    # Detect git commit (committing to current branch)
    is_commit = bool(re.search(r"\bgit\s+(?:.*\s)?commit\b", cmd))
    is_push = bool(re.search(r"\bgit\s+(?:.*\s)?push\b", cmd))

    if not (is_commit or is_push):
        return None

    branch = get_current_branch(cwd)
    if not branch:
        return None

    if branch.lower() not in TRUNK_BRANCHES:
        return None

    if is_commit:
        return (
            f"git commit on trunk branch '{branch}'",
            f"Branch '{branch}' is a trunk. Create a feature branch first:\n"
            f"  git -C <repo> checkout -b <type>/<desc>\n"
            f"Override only if intentional: add `# CONFIRMED-TRUNK-COMMIT`.",
        )
    # is_push
    # Allow pushing feature branch from trunk (e.g. push <branch> after merge cleanup).
    # Block: push without explicit branch arg (defaults to current trunk) OR push origin <trunk>.
    # Block: push origin <trunk-name> explicitly.
    push_to_trunk = re.search(
        rf"\bgit\s+(?:.*\s)?push\s+(?:[-a-zA-Z]+\s+)?\S+\s+({'|'.join(TRUNK_BRANCHES)})\b",
        cmd,
        flags=re.IGNORECASE,
    )
    # Plain `git push` (no args) — pushes current branch, which IS trunk
    bare_push = bool(re.search(r"\bgit\s+push\s*$", cmd.strip()))

    if push_to_trunk or bare_push:
        return (
            f"git push to trunk branch '{branch}'",
            f"Branch '{branch}' is trunk. Use a PR instead:\n"
            f"  1. Create feature branch from trunk\n"
            f"  2. Push feature branch\n"
            f"  3. Open PR via GitHub UI\n"
            f"Override only if intentional: add `# CONFIRMED-TRUNK-PUSH`.",
        )

    return None


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        print(f"[hook:block_dangerous_commands] could not parse stdin: {exc}", file=sys.stderr)
        return 0

    if data.get("agent_action_name") != "pre_run_command":
        return 0

    tool_info = data.get("tool_info", {}) or {}
    cmd = tool_info.get("command_line", "") or ""
    if not cmd.strip():
        return 0

    cmd_norm = cmd.strip()
    cwd = tool_info.get("cwd") or os.getcwd()

    # Layer 1: hard blocks
    for pattern, label in HARD_BLOCK_PATTERNS:
        if re.search(pattern, cmd_norm, flags=re.IGNORECASE):
            print(
                f"[hook:block_dangerous_commands] BLOCKED — matches hard-block rule "
                f"'{label}'.\n"
                f"Command: {cmd_norm}\n"
                f"This pattern is never auto-runnable. Run manually if intentional.",
                file=sys.stderr,
            )
            return 2

    # Layer 2: confirmed patterns
    has_confirm = bool(CONFIRM_TOKEN_RE.search(cmd_norm))
    for pattern, label, hint in CONFIRMED_PATTERNS:
        if re.search(pattern, cmd_norm, flags=re.IGNORECASE) and not has_confirm:
            print(
                f"[hook:block_dangerous_commands] BLOCKED — matches '{label}'.\n"
                f"Command: {cmd_norm}\n"
                f"Hint: {hint}\n"
                f"Or ask the user to run it manually in their own terminal.",
                file=sys.stderr,
            )
            return 2

    # Layer 3: trunk branch guard
    if not has_confirm:
        guard = check_trunk_guard(cmd_norm, cwd)
        if guard is not None:
            label, hint = guard
            print(
                f"[hook:block_dangerous_commands] BLOCKED — {label}.\n"
                f"Command: {cmd_norm}\n"
                f"Hint: {hint}",
                file=sys.stderr,
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
