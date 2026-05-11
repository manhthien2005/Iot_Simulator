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
"""

from __future__ import annotations

import json
import re
import sys

# ---- Patterns that are ALWAYS blocked (no override) -----------------------
# These are catastrophic destructive operations.
HARD_BLOCK_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+-[rRf]+\s+/(?:\s|$)", "rm -rf / (recursive root delete)"),
    (r"\brm\s+-[rRf]+\s+\*\s*$", "rm -rf * (recursive cwd wipe)"),
    (r"\brm\s+-[rRf]+\s+~\s*$", "rm -rf ~ (home directory wipe)"),
    (r"\bmkfs\.", "mkfs (filesystem format)"),
    (r"\bdd\s+if=.*of=/dev/[sh]d", "dd to raw disk device"),
    (r"\bformat\s+[a-zA-Z]:", "Windows format <drive>:"),
    (r"\bdel\s+/[fFsSqQ]+\s+/[fFsSqQ]+", "del /F /S /Q (recursive force delete)"),
    (r"\brmdir\s+/[sSqQ]+", "rmdir /S (recursive directory delete)"),
    (r":\(\)\s*\{.*:\|:.*\}\s*;\s*:", "fork bomb"),
]

# ---- Patterns that require explicit user confirmation in the command ------
# Block unless the command line itself contains an explicit confirmation token.
CONFIRMED_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"\bgit\s+push\s+(?:.*\s)?(?:-f|--force|--force-with-lease)\b.*\b(main|master|production|prod)\b",
        "git push --force on main/master/prod",
        "Add `# CONFIRMED-FORCE-PUSH` to the command, OR work on a feature branch.",
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
]

CONFIRMED_PATTERNS.extend([
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
])

CONFIRM_TOKEN_RE = re.compile(
    r"#\s*CONFIRMED-(?:FORCE-PUSH|PROD-DEPLOY|GCLOUD-DESTRUCTIVE|NPM-PUBLISH|PUB-PUBLISH"
    r"|RESET-HARD|FLUTTER-CLEAN|ADD-DEP|AUTH-PII)\b"
)


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        print(f"[hook:block_dangerous_commands] could not parse stdin: {exc}", file=sys.stderr)
        return 0

    if data.get("agent_action_name") != "pre_run_command":
        return 0

    cmd = (data.get("tool_info", {}) or {}).get("command_line", "") or ""
    if not cmd.strip():
        return 0

    cmd_norm = cmd.strip()

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

    return 0


if __name__ == "__main__":
    sys.exit(main())
