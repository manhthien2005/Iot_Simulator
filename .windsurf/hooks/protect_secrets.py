#!/usr/bin/env python3
"""
Protect secret/credential files from being read or modified by Cascade.

Listens on `pre_read_code` and `pre_write_code` hooks. Exits with code 2 to
block, 0 to allow.

Why pre_read_code too: even reading a service-account JSON pulls secrets into
the model context, where they may end up in a future response or memory.

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


def normalize_path(path: str) -> str:
    """Lowercase + forward-slashes for cross-platform pattern matching."""
    return path.replace("\\", "/").lower()


def is_allowlisted(path: str) -> bool:
    norm = normalize_path(path)
    return any(re.search(p, norm) for p in ALLOWLIST_PATTERNS)


def match_secret(path: str) -> str | None:
    """Return human-readable label if path matches a secret pattern, else None."""
    if not path:
        return None
    norm = normalize_path(path)
    for pattern, label in SECRET_FILE_PATTERNS:
        if re.search(pattern, norm):
            return label
    return None


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

    file_path = (data.get("tool_info", {}) or {}).get("file_path", "") or ""
    if not file_path:
        return 0

    if is_allowlisted(file_path):
        return 0

    label = match_secret(file_path)
    if label is None:
        return 0

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


if __name__ == "__main__":
    sys.exit(main())
