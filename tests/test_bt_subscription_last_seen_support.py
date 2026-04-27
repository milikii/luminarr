from __future__ import annotations

from pathlib import Path

from app.db.bt_subscription_repo import BtSubscriptionPersistenceError, BtSubscriptionRepo
from app.db.sqlite import SqliteDatabase
from app.services.manage_bt_subscription import update_bt_subscription_last_seen


def test_update_bt_subscription_last_seen_returns_updated_when_repo_write_succeeds(tmp_path: Path) -> None:
    repo = BtSubscriptionRepo(_make_database(tmp_path))
    created = repo.add_item(chat_id=1001, title="葬送的芙莉莲", year="2023", media_kind="anime")
    assert created is not None
    item, _ = created

    status = update_bt_subscription_last_seen(
        repo=repo,
        chat_id=1001,
        item_id=item.item_id,
        source="https://example.com/frieren-s01e01.torrent",
        title="Frieren S01E01 1080p",
        item_missing_reason="bt_subscription_item missing during last_seen update",
        result_missing_reason="bt subscription last_seen update result missing",
        is_item_row_corrupted_reason=lambda reason: "corrupted" in reason,
        log_item_missing=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
        log_result_missing=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
        log_row_corrupted=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
        log_update_failed=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
    )

    assert status == "updated"
    updated_item = repo.list_items(chat_id=1001)[0]
    assert updated_item.last_seen_source == "https://example.com/frieren-s01e01.torrent"
    assert updated_item.last_seen_title == "Frieren S01E01 1080p"


def test_update_bt_subscription_last_seen_returns_item_missing_and_logs_reason(tmp_path: Path) -> None:
    class MissingRowBtSubscriptionRepo(BtSubscriptionRepo):
        def update_last_seen(self, *, chat_id: int, item_id: int, source: str, title: str) -> bool:
            raise BtSubscriptionPersistenceError("bt_subscription_item missing during last_seen update")

    repo = MissingRowBtSubscriptionRepo(_make_database(tmp_path))
    reasons: list[str] = []

    status = update_bt_subscription_last_seen(
        repo=repo,
        chat_id=1001,
        item_id=1,
        source="https://example.com/frieren-s01e01.torrent",
        title="Frieren S01E01 1080p",
        item_missing_reason="bt_subscription_item missing during last_seen update",
        result_missing_reason="bt subscription last_seen update result missing",
        is_item_row_corrupted_reason=lambda reason: "corrupted" in reason,
        log_item_missing=reasons.append,
        log_result_missing=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
        log_row_corrupted=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
        log_update_failed=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
    )

    assert status == "item_missing"
    assert reasons == ["bt_subscription_item missing during last_seen update"]


def test_update_bt_subscription_last_seen_returns_persistence_failed_for_result_missing(tmp_path: Path) -> None:
    repo = BtSubscriptionRepo(_make_database(tmp_path))
    reasons: list[str] = []

    def _missing_update_last_seen(**_: object) -> None:
        return None

    repo.update_last_seen = _missing_update_last_seen  # type: ignore[method-assign]

    status = update_bt_subscription_last_seen(
        repo=repo,
        chat_id=1001,
        item_id=1,
        source="https://example.com/frieren-s01e01.torrent",
        title="Frieren S01E01 1080p",
        item_missing_reason="bt_subscription_item missing during last_seen update",
        result_missing_reason="bt subscription last_seen update result missing",
        is_item_row_corrupted_reason=lambda reason: "corrupted" in reason,
        log_item_missing=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
        log_result_missing=reasons.append,
        log_row_corrupted=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
        log_update_failed=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
    )

    assert status == "persistence_failed"
    assert reasons == ["bt subscription last_seen update result missing"]


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database
