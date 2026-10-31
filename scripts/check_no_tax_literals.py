"""Lint check enforcing ARCHITECTURE.md Rule A.1 and Rule A.2:

- Rule A.1: "Never invent a domain rule. Read from /jurisdiction/ma/*.yaml."
- Rule A.2 #2: "No numeric literals for tax or legal values outside `/jurisdiction/`.
  CI fails on 20, 10, 5000, 50000, 75, 100 used as rates or thresholds in application code.
  Account-code seeds and identifier regexes (ICE, IF, RIB) must be loaded from jurisdiction packs."
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FORBIDDEN_NUMBERS = {"20", "10", "5000", "50000", "75", "100", "0.20", "0.10", "0.75", "1.00"}

# Keywords indicating tax, rate, or legal threshold context (handles underscores like vat_rate)
TAX_CONTEXT_PATTERN = re.compile(
    r"(?:^|[\W_])(vat|tva|rate|threshold|withhold|retenue|taux|tax|cash_limit|plafond)(?:$|[\W_])",
    re.IGNORECASE,
)

# Forbidden identifier regex patterns outside jurisdiction packs
FORBIDDEN_IDENTIFIER_PATTERNS = [
    (re.compile(re.escape(r"^[0-9]{15}$")), "ICE 15-digit regex pattern hardcoded outside /jurisdiction/"),
    (re.compile(re.escape(r"^[0-9]{24}$")), "RIB 24-digit regex pattern hardcoded outside /jurisdiction/"),
    (re.compile(re.escape(r"^[0-9]{1,10}$")), "IF regex pattern hardcoded outside /jurisdiction/"),
]

# Forbidden hardcoded account seed patterns
FORBIDDEN_ACCOUNT_SEED_PATTERNS = [
    (re.compile(r"STANDARD_CGNC_ACCOUNTS\s*="), "Hardcoded STANDARD_CGNC_ACCOUNTS seed array in app code"),
    (re.compile(r'\{["\']code["\']\s*:\s*["\'](1111|3421|4411|5141|6111|7111)["\']'), "Hardcoded accounting account seed dictionary in app code"),
]

ROOT_DIR = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ROOT_DIR / "jurisdiction",
    ROOT_DIR / "fixtures",
    ROOT_DIR / "tests" / "fixtures",
    ROOT_DIR / "node_modules",
    ROOT_DIR / ".git",
    ROOT_DIR / "dist",
    ROOT_DIR / ".venv",
    ROOT_DIR / "__pycache__",
}


def is_excluded(path: Path) -> bool:
    for exc in EXCLUDE_DIRS:
        if exc in path.parents or path == exc:
            return True
    return False


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    violations: list[tuple[int, str, str]] = []
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return violations

    lines = content.splitlines()
    in_docstring = False

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Handle comments
        if stripped.startswith(("#", "//", "/*", "*")):
            continue

        # Handle multi-line docstrings
        if stripped.startswith(('"""', "'''")):
            quote = '"""' if stripped.startswith('"""') else "'''"
            if stripped.count(quote) == 1:
                in_docstring = not in_docstring
                continue
            elif stripped.count(quote) >= 2:
                # Single-line docstring: """ ... """
                continue

        if in_docstring:
            if '"""' in stripped or "'''" in stripped:
                in_docstring = False
            continue

        # 1. Tax/rate forbidden numbers
        if TAX_CONTEXT_PATTERN.search(line):
            for num in FORBIDDEN_NUMBERS:
                if re.search(rf"(?<![\w.]){re.escape(num)}(?![\w.])", line):
                    violations.append((idx, f"tax literal '{num}'", line.strip()))

        # 2. Hardcoded identifier regexes
        for pat, desc in FORBIDDEN_IDENTIFIER_PATTERNS:
            if pat.search(line):
                violations.append((idx, desc, line.strip()))

        # 3. Hardcoded account seeds
        for pat, desc in FORBIDDEN_ACCOUNT_SEED_PATTERNS:
            if pat.search(line):
                violations.append((idx, desc, line.strip()))

    return violations


def main() -> int:
    scan_dirs = [
        ROOT_DIR / "avenel",
        ROOT_DIR / "apps",
    ]

    total_violations = 0
    for d in scan_dirs:
        if not d.exists():
            continue
        for ext in ("*.py", "*.ts", "*.tsx", "*.js"):
            for file_path in d.rglob(ext):
                if is_excluded(file_path):
                    continue
                violations = scan_file(file_path)
                for line_no, reason, line in violations:
                    print(
                        f"[LINT ERROR - Rule A.1 & A.2] {file_path.relative_to(ROOT_DIR)}:{line_no}: "
                        f"{reason}: {line}"
                    )
                    total_violations += 1

    if total_violations > 0:
        print(f"\nFailed with {total_violations} domain/tax literal violation(s).")
        print("Read every tax rate, threshold, deadline, account seed, and identifier regex from /jurisdiction/ma/*.yaml instead.")
        return 1

    print("[LINT PASSED] No forbidden numeric tax literals, hardcoded identifier regexes, or account seeds found in application code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
