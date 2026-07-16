"""Tests for the Polar export directory scanner / file classifier."""

from pathlib import Path

import pytest

from garminview.ingestion.polar.scanner import classify_file, scan_directory


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("training-session-332906208.json", "training-session"),
        ("activity-2024-01-15.json", "activity"),
        ("sleep_result_123.json", "sleep"),
        ("247ohr_123.json", "247ohr"),
        ("fitness-test-results-123.json", "fitness-test"),
        ("training-target-123.json", "training-target"),
        ("account-data-17498985-abcd.json", "account-data"),
        ("account-profile-17498985-abcd.json", "account-profile"),
        ("calendar-items-123.json", "calendar"),
        ("sport-profiles-123.json", "sport-profiles"),
        ("products-devices-123.json", "devices"),
        ("programs-eventtrainingprograms-123.json", "programs"),
        ("planned-route-1.json", "planned-route"),
        ("favourite-targets-1.json", "favourite-targets"),
        ("some-random-file.json", None),
    ],
)
def test_classify_file(filename, expected):
    assert classify_file(filename) == expected


def test_scan_directory_groups_by_type(tmp_path):
    for name in (
        "training-session-1.json",
        "training-session-2.json",
        "activity-2024-01-15.json",
        "sleep_result_1.json",
        "mystery.json",
    ):
        (tmp_path / name).write_text("{}")

    result = scan_directory(tmp_path)
    assert len(result["training-session"]) == 2
    assert len(result["activity"]) == 1
    assert len(result["sleep"]) == 1
    assert len(result["unknown"]) == 1
    # every value is a list of Paths
    assert all(isinstance(p, Path) for group in result.values() for p in group)


def test_scan_directory_ignores_non_json(tmp_path):
    (tmp_path / "activity-2024-01-15.json").write_text("{}")
    (tmp_path / "readme.txt").write_text("hi")
    (tmp_path / "notes.csv").write_text("a,b")
    result = scan_directory(tmp_path)
    assert set(result.keys()) == {"activity"}


def test_scan_directory_missing_dir_raises():
    with pytest.raises(FileNotFoundError):
        scan_directory("/nonexistent/path/xyz")


def test_scan_directory_empty(tmp_path):
    assert scan_directory(tmp_path) == {}
