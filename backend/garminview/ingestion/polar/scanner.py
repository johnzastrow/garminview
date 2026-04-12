"""Scan a Polar Flow GDPR export directory and categorize files by type."""

import re
from pathlib import Path

# Maps file prefix patterns to logical type names.
# Order matters — first match wins.
_PREFIX_RULES: list[tuple[str, str]] = [
    (r"^training-session-", "training-session"),
    (r"^activity-", "activity"),
    (r"^sleep_result_", "sleep"),
    (r"^247ohr_", "247ohr"),
    (r"^fitness-test-results-", "fitness-test"),
    (r"^training-target-", "training-target"),
    (r"^account-data-", "account-data"),
    (r"^account-profile-", "account-profile"),
    (r"^calendar-items-", "calendar"),
    (r"^sport-profiles-", "sport-profiles"),
    (r"^products-devices-", "devices"),
    (r"^programs-", "programs"),
    (r"^planned-route-", "planned-route"),
    (r"^favourite-targets-", "favourite-targets"),
]

_COMPILED = [(re.compile(pat), ft) for pat, ft in _PREFIX_RULES]


def classify_file(filename: str) -> str | None:
    """Return the file type for a Polar export filename, or None if unrecognized."""
    for pattern, file_type in _COMPILED:
        if pattern.search(filename):
            return file_type
    return None


def scan_directory(path: str | Path) -> dict[str, list[Path]]:
    """Scan a directory for Polar export JSON files grouped by type.

    Returns a dict like {"training-session": [Path(...), ...], "activity": [...], ...}.
    Unrecognized files are grouped under "unknown".
    """
    root = Path(path)
    if not root.is_dir():
        raise FileNotFoundError(f"Not a directory: {root}")

    result: dict[str, list[Path]] = {}
    for f in sorted(root.glob("*.json")):
        file_type = classify_file(f.name) or "unknown"
        result.setdefault(file_type, []).append(f)

    return result
