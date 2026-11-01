"""CI check to ensure test collection count does not decrease without justification.

Fails if collected pytest test count is lower than the recorded baseline
unless a TESTS_REMOVED.md file is present in the repository explaining the removal.
"""

from __future__ import annotations

import os
import subprocess
import sys

BASELINE_FILE = os.path.join(os.path.dirname(__file__), "..", "tests", ".test_count_baseline")
REMOVAL_EXPLANATION_FILE = os.path.join(os.path.dirname(__file__), "..", "TESTS_REMOVED.md")
MINIMUM_BASELINE = 107


def get_baseline_count() -> int:
    if os.path.exists(BASELINE_FILE):
        try:
            with open(BASELINE_FILE, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val.isdigit():
                    return max(int(val), MINIMUM_BASELINE)
        except OSError:
            pass
    return MINIMUM_BASELINE


def get_collected_count() -> int:
    # Use sys.executable to run pytest --collect-only -q
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output = proc.stdout + proc.stderr
    if proc.returncode != 0:
        print(f"[COLLECTION WARNING] pytest --collect-only returned code {proc.returncode}:\n{output}", file=sys.stderr)

    count = 0
    for line in output.splitlines():
        line = line.strip()
        if "::" in line:
            count += 1
        elif "collected" in line and "items" in line:
            # e.g. "collected 107 items"
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "collected" and i + 1 < len(parts) and parts[i + 1].isdigit():
                    count = max(count, int(parts[i + 1]))
        elif "tests collected" in line:
            # e.g. "107 tests collected"
            parts = line.split()
            if parts and parts[0].isdigit():
                count = max(count, int(parts[0]))
    return count


def main() -> int:
    baseline = get_baseline_count()
    collected = get_collected_count()

    print(f"[TEST COUNT CHECK] Collected: {collected} | Required Baseline: {baseline}")

    if collected < baseline:
        if os.path.exists(REMOVAL_EXPLANATION_FILE):
            print(f"[INFO] Test count decreased ({collected} < {baseline}), but TESTS_REMOVED.md is present.")
            return 0
        else:
            print(
                f"[ERROR] Test count dropped from {baseline} to {collected}!\n"
                f"Decreasing test count is prohibited unless TESTS_REMOVED.md exists explaining the reason.",
                file=sys.stderr,
            )
            return 1

    # If count increased, record the new high watermark in baseline file
    if collected > baseline:
        try:
            with open(BASELINE_FILE, "w", encoding="utf-8") as f:
                f.write(str(collected) + "\n")
            print(f"[INFO] Updated test count baseline to {collected}.")
        except OSError:
            pass

    print("[TEST COUNT CHECK PASSED] Test count maintained or increased.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

