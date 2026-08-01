"""Fail when legacy product branding leaks into user-facing source files.

Compatibility-only route, storage, provider, and fixture identifiers are allowed.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"(?:\b(?:ACE|Ace)\b|acehr\.app)", re.IGNORECASE)
SCANNED_SUFFIXES = {".js", ".jsx", ".py", ".html", ".md", ".example"}

ALLOWLIST = {
    "frontend/src/App.jsx": {"/ask-ace"},
    "frontend/src/utils/tenantScope.js": {"ace.activeTenantId"},
    "backend/app/services/signature_service.py": {"'ace'"},
    "backend/app/services/signature_evidence_service.py": {"'ace'"},
    "backend/app/tests/test_dropbox_sign_evidence_download.py": {"ace-request-1"},
    "backend/app/tests/test_dropbox_sign_provider.py": {"ace-request-1"},
    "docs/KINETIC_REDESIGN.md": {
        "Ace → Kinetic",
        "Ace references",
        "/ask-ace",
        "ace.activeTenantId",
        "value `ace`",
        "ace-request-1",
        "No user-facing Ace",
    },
}


def allowed(relative: str, line: str) -> bool:
    return any(token in line for token in ALLOWLIST.get(relative, set()))


def main() -> int:
    violations: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "node_modules" in path.parts:
            continue
        if path.suffix not in SCANNED_SUFFIXES and path.name != ".env.example":
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative == 'scripts/verify_kinetic_branding.py':
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if PATTERN.search(line) and not allowed(relative, line):
                violations.append(f"{relative}:{number}: {line.strip()}")

    if violations:
        print("Legacy user-facing branding found:")
        print("\n".join(violations))
        return 1

    print("Kinetic branding verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
