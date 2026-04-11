from __future__ import annotations

from pathlib import Path

import pytest

from app.maintenance.cleanup_verification_docs import (
    CleanupVerificationDocsSyncError,
    SNAPSHOT_SPECS,
    SnapshotRun,
    parse_pytest_result,
    update_status_text,
    update_window_text,
)


def test_parse_pytest_result_strips_duration_suffix() -> None:
    stdout = "...\n724 passed, 2 skipped in 33.21s\n"

    assert parse_pytest_result(stdout) == "724 passed, 2 skipped"


def test_parse_pytest_result_strips_duration_suffix_with_clock_format() -> None:
    stdout = "...\n384 passed in 109.83s (0:01:49)\n"

    assert parse_pytest_result(stdout) == "384 passed"


def test_parse_pytest_result_raises_for_unexpected_summary() -> None:
    with pytest.raises(CleanupVerificationDocsSyncError):
        parse_pytest_result("no useful summary here\n")


def test_update_status_text_replaces_date_first_and_result_first_entries() -> None:
    original = (
        "## Latest verification\n\n"
        "- tests：2026-04-10，`700 passed`（`.venv/bin/python -m pytest -q`）\n"
        "- four-channel cleanup smoke tests：`370 passed`（2026-04-10，"
        "`old smoke command`）\n"
    )
    runs = [
        SnapshotRun(
            spec=SNAPSHOT_SPECS["full_suite"],
            date_text="2026-04-11",
            result_text="724 passed, 2 skipped",
        ),
        SnapshotRun(
            spec=SNAPSHOT_SPECS["smoke_gate"],
            date_text="2026-04-11",
            result_text="376 passed",
        ),
    ]

    updated = update_status_text(original, runs)

    assert "- tests：2026-04-11，`724 passed, 2 skipped`（`.venv/bin/python -m pytest -q`）" in updated
    assert (
        "- four-channel cleanup smoke tests：`376 passed`"
        "（2026-04-11，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）"
    ) in updated


def test_update_window_text_replaces_verification_evidence_entry() -> None:
    original = (
        "## Verification evidence\n\n"
        "- 最近一次聚合 smoke gate：2026-04-10，`370 passed`（`old smoke command`）\n"
    )
    runs = [
        SnapshotRun(
            spec=SNAPSHOT_SPECS["smoke_gate"],
            date_text="2026-04-11",
            result_text="376 passed",
        ),
    ]

    updated = update_window_text(original, runs)

    assert (
        "- 最近一次聚合 smoke gate：2026-04-11，`376 passed`"
        "（`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）"
    ) in updated


def test_update_status_text_raises_when_label_is_missing() -> None:
    run = SnapshotRun(
        spec=SNAPSHOT_SPECS["docs_consistency"],
        date_text="2026-04-11",
        result_text="passed",
    )

    with pytest.raises(CleanupVerificationDocsSyncError):
        update_status_text("## Latest verification\n", [run])
