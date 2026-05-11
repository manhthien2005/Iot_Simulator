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
2. CONFIRMED_PATTERNS — needs explicit `# CONFIRMED-<SPECIFIC-TOKEN>` matching the pattern
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

# ---- Reusable git prefix that handles `git -C <repo>` variants ------------
# Matches: "git ", "git -C path ", "git -C \"path with space\" ", "git -C 'path' "
# Used in CONFIRMED_PATTERNS so subcommand checks (push --force, reset --hard,
# clean -fdx) work regardless of whether `-C <repo>` is present.
GIT_PREFIX = r"\bgit\s+(?:-C\s+(?:\"[^\"]+\"|'[^']+'|\S+)\s+)?"

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
# Each entry: (pattern, label, required_token, hint)
# Token is scoped per-pattern. "# CONFIRMED-GIT-CLEAN" does NOT bypass "git push --force".
CONFIRMED_PATTERNS: list[tuple[str, str, str, str]] = [
    (
        rf"{GIT_PREFIX}push\s+(?:.*\s)?(?:-f|--force|--force-with-lease)\b",
        "git push --force",
        "CONFIRMED-FORCE-PUSH",
        "Add `# CONFIRMED-FORCE-PUSH` to the command, OR use --force-with-lease on a feature branch.",
    ),
    (
        r"\bfirebase\s+(?:deploy|firestore:delete|database:remove)\b.*--project[= ](?:.*?)(?:prod|production)",
        "firebase destructive op against prod project",
        "CONFIRMED-PROD-DEPLOY",
        "Add `# CONFIRMED-PROD-DEPLOY` to the command after a manual review.",
    ),
    (
        r"\bgcloud\s+(?:.*\s)?(?:projects\s+delete|sql\s+databases\s+delete|storage\s+rm\s+-r)",
        "gcloud destructive operation",
        "CONFIRMED-GCLOUD-DESTRUCTIVE",
        "Add `# CONFIRMED-GCLOUD-DESTRUCTIVE` to the command line.",
    ),
    (
        r"\bnpm\s+(?:publish|unpublish)\b",
        "npm publish/unpublish",
        "CONFIRMED-NPM-PUBLISH",
        "Add `# CONFIRMED-NPM-PUBLISH` if intentional.",
    ),
    (
        r"\bpub\s+publish\b",
        "dart pub publish",
        "CONFIRMED-PUB-PUBLISH",
        "Add `# CONFIRMED-PUB-PUBLISH` if intentional.",
    ),
    (
        rf"{GIT_PREFIX}reset\s+(?:.*\s)?--hard\b",
        "git reset --hard (destructive — drops uncommitted work)",
        "CONFIRMED-RESET-HARD",
        "Add `# CONFIRMED-RESET-HARD` if you really want to discard local changes.",
    ),
    (
        r"\bflutter\s+clean\b",
        "flutter clean (forbidden auto-run per personal-operating-mode rule)",
        "CONFIRMED-FLUTTER-CLEAN",
        "Add `# CONFIRMED-FLUTTER-CLEAN` if you intentionally want to wipe build cache.",
    ),
    (
        rf"{GIT_PREFIX}clean\s+-[fdx]+",
        "git clean -fdx (deletes untracked files including ignored)",
        "CONFIRMED-GIT-CLEAN",
        "Add `# CONFIRMED-GIT-CLEAN` if intentional.",
    ),
    (
        r"\b(?:npm\s+(?:install|i)|yarn\s+add|pnpm\s+(?:add|install))\s+(?:-[^\s]*\s+)*[a-zA-Z@][^\s]*",
        "npm/yarn/pnpm install <package> (adds new dependency — discuss first)",
        "CONFIRMED-ADD-DEP",
        "Add `# CONFIRMED-ADD-DEP` after deciding on the package + version with the user.",
    ),
    (
        r"\b(?:flutter\s+pub\s+add|dart\s+pub\s+add)\s+[a-zA-Z][^\s]*",
        "flutter/dart pub add <package> (adds new dependency — discuss first)",
        "CONFIRMED-ADD-DEP",
        "Add `# CONFIRMED-ADD-DEP` after deciding on the package + version with the user.",
    ),
    (
        r"\bfirebase\s+auth:(?:export|import)\b",
        "firebase auth:export/import (PII bulk read/write)",
        "CONFIRMED-AUTH-PII",
        "Add `# CONFIRMED-AUTH-PII` after manual security review.",
    ),
    (
        r"\bnpx\s+prisma\s+(?:db\s+push|migrate\s+deploy)\b",
        "Prisma db push / migrate deploy (production schema change)",
        "CONFIRMED-PRISMA-DEPLOY",
        "Add `# CONFIRMED-PRISMA-DEPLOY` after backup verified.",
    ),
]


def has_token(cmd: str, token: str) -> bool:
    """Check if the command contains the EXACT confirmation token.

    Must be followed by end-of-string or whitespace (NOT a word char or hyphen),
    so `CONFIRMED-FORCE-PUSH` does not match inside `CONFIRMED-FORCE-PUSH-EXTRA`.
    """
    return bool(re.search(rf"#\s*{re.escape(token)}(?![\w\-])", cmd))


def extract_git_c_path(cmd: str) -> str | None:
    """If command uses `git -C <path>`, return the path. Else None.

    Handles quoted paths: git -C "d:\\path with space" ...
    """
    # Match: git (?) -C <path>
    # Path can be: quoted "..." / '...' / unquoted non-whitespace run
    m = re.search(
        r"\bgit\s+(?:.*?\s+)?-C\s+(?:\"([^\"]+)\"|'([^']+)'|(\S+))",
        cmd,
    )
    if not m:
        return None
    return m.group(1) or m.group(2) or m.group(3)


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
    """If command is git commit/push and target repo branch is trunk, return (label, hint).

    Target repo = path from `git -C <path>` if present, else `cwd`.
    """
    is_commit = bool(re.search(r"\bgit\s+(?:.*\s)?commit\b", cmd))
    is_push = bool(re.search(r"\bgit\s+(?:.*\s)?push\b", cmd))

    if not (is_commit or is_push):
        return None

    # Resolve target repo: prefer -C path, fallback to cwd.
    git_c_path = extract_git_c_path(cmd)
    target_cwd = git_c_path or cwd
    branch = get_current_branch(target_cwd)
    if not branch:
        return None

    if branch.lower() not in TRUNK_BRANCHES:
        return None

    if is_commit:
        return (
            f"git commit on trunk branch '{branch}' (target: {target_cwd})",
            f"Branch '{branch}' is a trunk. Create a feature branch first:\n"
            f"  git -C <repo> checkout -b <type>/<desc>\n"
            f"Override only if intentional: add `# CONFIRMED-TRUNK-COMMIT`.",
        )

    # is_push — block these when on trunk:
    #   - git push                             (bare: pushes current = trunk)
    #   - git push <remote>                    (pushes current = trunk by default)
    #   - git push <remote> <trunk>            (explicit trunk target)
    #   - git push <remote> HEAD:<trunk>       (explicit trunk target via HEAD)
    # Allow: git push <remote> <feature-branch> (feature branch cleanup)
    trunks_re = "|".join(TRUNK_BRANCHES)

    # Explicit push to trunk (remote + trunk ref or HEAD:trunk)
    push_to_trunk_explicit = re.search(
        rf"\bgit\s+(?:.*\s)?push\s+(?:[-a-zA-Z]+\s+)*\S+\s+(?:HEAD:)?({trunks_re})\b",
        cmd,
        flags=re.IGNORECASE,
    )
    # Bare `git push` (no args beyond flags)
    bare_push = bool(
        re.search(
            r"\bgit\s+(?:-C\s+\S+\s+|-C\s+\"[^\"]+\"\s+|-C\s+'[^']+'\s+)?push\s*(?:-[a-zA-Z]\S*\s*)*$",
            cmd.strip(),
        )
    )
    # `git push <remote>` with no branch — pushes current (=trunk)
    push_remote_only = bool(
        re.search(
            r"\bgit\s+(?:-C\s+\S+\s+|-C\s+\"[^\"]+\"\s+|-C\s+'[^']+'\s+)?"
            r"push\s+(?:-[a-zA-Z]\S*\s+)*[a-zA-Z][\w.-]*\s*$",
            cmd.strip(),
        )
    )

    if push_to_trunk_explicit or bare_push or push_remote_only:
        return (
            f"git push to trunk branch '{branch}' (target: {target_cwd})",
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

    # Layer 2: confirmed patterns (pattern-scoped tokens)
    for pattern, label, token, hint in CONFIRMED_PATTERNS:
        if re.search(pattern, cmd_norm, flags=re.IGNORECASE) and not has_token(cmd_norm, token):
            print(
                f"[hook:block_dangerous_commands] BLOCKED — matches '{label}'.\n"
                f"Command: {cmd_norm}\n"
                f"Hint: {hint}\n"
                f"Or ask the user to run it manually in their own terminal.",
                file=sys.stderr,
            )
            return 2

    # Layer 3: trunk branch guard
    guard = check_trunk_guard(cmd_norm, cwd)
    if guard is not None:
        label, hint = guard
        # Pattern-scoped tokens for trunk guard
        if "commit" in label and has_token(cmd_norm, "CONFIRMED-TRUNK-COMMIT"):
            return 0
        if "push" in label and has_token(cmd_norm, "CONFIRMED-TRUNK-PUSH"):
            return 0
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
