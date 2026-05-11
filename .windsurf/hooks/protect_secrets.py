#!/usr/bin/env python3
"""
Protect secret/credential files + content from being read or modified by Cascade.

Listens on `pre_read_code` and `pre_write_code` hooks. Exits with code 2 to
block, 0 to allow.

Two-layer protection:
1. Filename pattern — blocks .env, .pem, service-account.json, etc.
2. Content pattern (write only) — scans new_string for embedded secrets
   (API keys, JWT secrets, hardcoded passwords, AWS credentials).

Why pre_read_code: even reading a service-account JSON pulls secrets into
the model context.

`.env.example` and similar template files are explicitly allowlisted.
"""

from __future__ import annotations

import json
import re
import sys

# ---- Filename patterns considered secrets ---------------------------------
SECRET_FILE_PATTERNS: list[tuple[str, str]] = [
    (r"(^|[\\/])\.env(\.[^\\/]+)?$", ".env file"),
    (r"(^|[\\/])\.envrc$", ".envrc (direnv)"),
    (r"\.pem$", "PEM private key"),
    (r"\.key$", "raw key file"),
    (r"\.p12$", "PKCS#12 keystore"),
    (r"\.pfx$", "PFX keystore"),
    (r"\.keystore$", "Java keystore"),
    (r"\.jks$", "Java keystore"),
    (r"(^|[\\/])key\.properties$", "Android signing config"),
    (r"firebase-adminsdk[^\\/]*\.json$", "Firebase Admin SDK service account"),
    (r"(^|[\\/])serviceAccount[^\\/]*\.json$", "service account JSON"),
    (r"(^|[\\/])google-services\.json$", "Android google-services.json"),
    (r"(^|[\\/])GoogleService-Info\.plist$", "iOS GoogleService-Info.plist"),
    (r"(^|[\\/])\.npmrc$", ".npmrc (may contain auth tokens)"),
    (r"(^|[\\/])id_rsa$|id_ed25519$|id_ecdsa$", "SSH private key"),
    (r"\.ovpn$", "OpenVPN config"),
    (r"\.kubeconfig$|(^|[\\/])kubeconfig$", "Kubernetes config"),
    (r"(^|[\\/])credentials(\.[^\\/]+)?$", "credentials file"),
]

# ---- Allowlist (templates, examples, documentation) ----------------------
ALLOWLIST_PATTERNS: list[str] = [
    r"\.env\.example$",
    r"\.env\.sample$",
    r"\.env\.template$",
    r"\.envrc\.example$",
    r"firebase-adminsdk[^\\/]*\.example\.json$",
    r"google-services\.example\.json$",
]

# ---- Content patterns (scan write content for embedded secrets) -----------
# Scan tool_info.edits[].new_string and tool_info.code_edit (single edits)
# for hardcoded secrets in code being written.
CONTENT_SECRET_PATTERNS: list[tuple[str, str]] = [
    # AWS access keys
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key ID"),
    (r"\baws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}['\"]?", "AWS secret access key"),
    # Generic API keys (long random strings assigned to "key"-named vars)
    (
        r"(?i)(?:api[_-]?key|apikey|secret[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9_\-+=/]{20,}['\"]",
        "hardcoded API/secret key",
    ),
    # JWT secret (specifically the ENV var or assignment)
    (
        r"(?i)(?:jwt[_-]?secret|jwt[_-]?key)\s*[:=]\s*['\"][^'\"]{16,}['\"]",
        "hardcoded JWT secret",
    ),
    # Postgres/DB connection strings with embedded password
    (
        r"(?:postgres|postgresql|mysql|mongodb)://[^:\s'\"]+:[^@\s'\"]{6,}@",
        "DB connection string with password",
    ),
    # Hardcoded passwords (length>=8, in obvious context)
    (
        r"(?i)(?:password|passwd|pwd)\s*[:=]\s*['\"](?!(?:your[_-]?|example|test|placeholder|change[_-]?me|<.*>))[^'\"\s]{8,}['\"]",
        "hardcoded password",
    ),
    # Firebase API keys (start with AIza, length 39)
    (r"\bAIza[0-9A-Za-z_-]{35}\b", "Firebase/Google API key"),
    # GitHub personal access tokens
    (r"\bghp_[A-Za-z0-9]{36,}\b", "GitHub personal access token"),
    (r"\bgho_[A-Za-z0-9]{36,}\b", "GitHub OAuth token"),
    # Slack tokens
    (r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b", "Slack token"),
    # Stripe live keys
    (r"\bsk_live_[A-Za-z0-9]{24,}\b", "Stripe live secret key"),
    # Private key blocks
    (r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", "PEM private key block"),
]


def normalize_path(path: str) -> str:
    """Lowercase + forward-slashes for cross-platform pattern matching."""
    return path.replace("\\", "/").lower()


def is_allowlisted(path: str) -> bool:
    norm = normalize_path(path)
    return any(re.search(p, norm) for p in ALLOWLIST_PATTERNS)


def match_secret_path(path: str) -> str | None:
    """Return human-readable label if path matches a secret pattern, else None."""
    if not path:
        return None
    norm = normalize_path(path)
    for pattern, label in SECRET_FILE_PATTERNS:
        if re.search(pattern, norm):
            return label
    return None


def scan_content_for_secrets(content: str) -> list[tuple[str, str]]:
    """Return list of (matched_snippet, label) for secrets found in content."""
    if not content:
        return []
    findings: list[tuple[str, str]] = []
    for pattern, label in CONTENT_SECRET_PATTERNS:
        match = re.search(pattern, content)
        if match:
            # Truncate matched snippet to avoid leaking the full secret in error
            snippet = match.group(0)[:60]
            findings.append((snippet, label))
    return findings


def extract_write_content(tool_info: dict) -> list[str]:
    """Extract new_string content from various write tool shapes."""
    contents: list[str] = []
    # multi_edit: edits array
    edits = tool_info.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict):
                ns = edit.get("new_string")
                if isinstance(ns, str):
                    contents.append(ns)
    # single edit: new_string
    ns = tool_info.get("new_string")
    if isinstance(ns, str):
        contents.append(ns)
    # write_to_file: code_content / CodeContent
    for key in ("code_content", "CodeContent", "content"):
        c = tool_info.get(key)
        if isinstance(c, str):
            contents.append(c)
    return contents


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        print(f"[hook:protect_secrets] could not parse stdin: {exc}", file=sys.stderr)
        return 0

    action = data.get("agent_action_name", "")
    if action not in ("pre_read_code", "pre_write_code"):
        return 0

    tool_info = data.get("tool_info", {}) or {}
    file_path = tool_info.get("file_path", "") or ""

    # Layer 1: filename-based block
    if file_path and not is_allowlisted(file_path):
        label = match_secret_path(file_path)
        if label is not None:
            verb = "read from" if action == "pre_read_code" else "write to"
            print(
                f"[hook:protect_secrets] BLOCKED — refusing to {verb} '{file_path}'.\n"
                f"Reason: file matches '{label}' pattern and may contain credentials.\n"
                f"If you genuinely need this file inspected, ask the user to share "
                f"the relevant content manually, or rename the file to a non-secret "
                f"path.",
                file=sys.stderr,
            )
            return 2

    # Layer 2: content-based block (write actions only)
    if action == "pre_write_code":
        for content in extract_write_content(tool_info):
            findings = scan_content_for_secrets(content)
            if findings:
                msgs = [f"  - {label}: '{snippet}...'" for snippet, label in findings[:3]]
                print(
                    f"[hook:protect_secrets] BLOCKED — content contains secret-like patterns "
                    f"in '{file_path}':\n" + "\n".join(msgs) + "\n"
                    f"Move secrets to .env (gitignored). Use placeholder in code.",
                    file=sys.stderr,
                )
                return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
