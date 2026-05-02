# Adult Duplicate Memory Execution Plan

> **For agentic workers:** Follow the Trellis execute loop: use `trellis-implement` to carry each task slice, then `trellis-check` to close verification. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the first executable slice of Stage 1 by adding an adult-only duplicate-memory guard that warns before creating pending downloads, keeps exact-code evidence in SQLite, and requires explicit operator override to continue.

**Architecture:** Add a new sibling snapshot truth table and repo, then build one shared duplicate-memory service that reads exact-code evidence from local adult directories, `adult_content_registry`, and historical job events. Wire that service into the `AddToDownloaderService` shared path so direct BT, batch preview, and `btsub` all reuse the same gate, with `bt_pending_state` carrying the explicit override follow-up.

**Tech Stack:** Python 3.12, SQLite repos in `app/db`, shared services in `app/services`, private-chat follow-up routing in `app/bot`, pytest, pyflakes, existing `make quality` / `make verify-mainline` / `make verify-adult-bt-wedge` gates

---

### Task 1: Add Snapshot Truth For Adult Duplicate Memory

**Files:**
- Create: `app/db/adult_duplicate_memory_snapshot_repo.py`
- Modify: `app/db/sqlite.py`
- Test: `tests/test_persistence_sqlite.py`

- [ ] **Step 1: Write the failing persistence test**

```python
def test_adult_duplicate_memory_snapshot_repo_round_trip(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "adult-duplicate.sqlite3"))
    database.initialize()

    repo = AdultDuplicateMemorySnapshotRepo(database)
    repo.upsert_snapshot(
        normalized_content_id="censored:ssis-123",
        display_title="SSIS-123",
        snapshot_status="fresh",
        evidence_summary_json=json.dumps(
            {
                "local_matches": [{"path": "/library/adult/SSIS-123.mp4"}],
                "registry_status": "archived_present",
                "event_hits": [{"event_type": "downloader.succeeded", "task_ref": "bt-1"}],
            },
            ensure_ascii=False,
        ),
        last_verified_at="2026-04-30T10:00:00+08:00",
        last_scan_failed_at="",
    )

    row = repo.get_snapshot("censored:ssis-123")

    assert row is not None
    assert row.normalized_content_id == "censored:ssis-123"
    assert row.snapshot_status == "fresh"
    assert "SSIS-123.mp4" in row.evidence_summary_json
```

- [ ] **Step 2: Run the focused persistence test and verify it fails**

Run: `.venv/bin/python -m pytest -q tests/test_persistence_sqlite.py -k adult_duplicate_memory_snapshot_repo_round_trip`

Expected: `FAIL` with `ImportError` or missing-table failure because the repo and schema do not exist yet.

- [ ] **Step 3: Write the minimal schema and repo implementation**

```python
@dataclass(frozen=True, slots=True)
class AdultDuplicateMemorySnapshotRecord:
    normalized_content_id: str
    display_title: str
    snapshot_status: str
    evidence_summary_json: str
    last_verified_at: str
    last_scan_failed_at: str
    created_at: str
    updated_at: str


class AdultDuplicateMemorySnapshotRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def get_snapshot(self, normalized_content_id: str) -> AdultDuplicateMemorySnapshotRecord | None:
        row = self._database.fetch_one(
            """
            SELECT normalized_content_id, display_title, snapshot_status, evidence_summary_json,
                   last_verified_at, last_scan_failed_at, created_at, updated_at
            FROM adult_duplicate_memory_snapshot
            WHERE normalized_content_id = ?
            """,
            (normalized_content_id,),
        )
        if row is None:
            return None
        return AdultDuplicateMemorySnapshotRecord(**dict(row))

    def upsert_snapshot(
        self,
        *,
        normalized_content_id: str,
        display_title: str,
        snapshot_status: str,
        evidence_summary_json: str,
        last_verified_at: str,
        last_scan_failed_at: str,
    ) -> AdultDuplicateMemorySnapshotRecord:
        now = utc_now_iso()
        self._database.execute(
            """
            INSERT INTO adult_duplicate_memory_snapshot (
                normalized_content_id,
                display_title,
                snapshot_status,
                evidence_summary_json,
                last_verified_at,
                last_scan_failed_at,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(normalized_content_id) DO UPDATE SET
                display_title = excluded.display_title,
                snapshot_status = excluded.snapshot_status,
                evidence_summary_json = excluded.evidence_summary_json,
                last_verified_at = excluded.last_verified_at,
                last_scan_failed_at = excluded.last_scan_failed_at,
                updated_at = excluded.updated_at
            """,
            (
                normalized_content_id,
                display_title,
                snapshot_status,
                evidence_summary_json,
                last_verified_at,
                last_scan_failed_at,
                now,
                now,
            ),
        )
        row = self.get_snapshot(normalized_content_id)
        if row is None:
            raise AdultDuplicateMemorySnapshotPersistenceError("adult_duplicate_memory_snapshot missing after upsert")
        return row
```

- [ ] **Step 4: Re-run the persistence test and keep it green**

Run: `.venv/bin/python -m pytest -q tests/test_persistence_sqlite.py -k adult_duplicate_memory_snapshot_repo_round_trip`

Expected: `1 passed`

- [ ] **Step 5: Commit the schema slice**

```bash
git add app/db/sqlite.py app/db/adult_duplicate_memory_snapshot_repo.py tests/test_persistence_sqlite.py
git commit -m "feat: add adult duplicate snapshot truth"
```

### Task 2: Build The Shared Adult Duplicate Memory Service

**Files:**
- Create: `app/services/adult_duplicate_memory.py`
- Modify: `app/services/adult_content.py`
- Test: `tests/test_adult_duplicate_memory.py`

- [ ] **Step 1: Write the failing service test**

```python
def test_adult_duplicate_memory_service_prefers_exact_id_evidence(tmp_path: Path) -> None:
    adult_dir = tmp_path / "adult"
    adult_dir.mkdir()
    (adult_dir / "SSIS-123 sample.mp4").write_text("video", encoding="utf-8")

    service = AdultDuplicateMemoryService(
        snapshot_repo=FakeSnapshotRepo(),
        adult_content_registry_repo=FakeAdultRegistryRepo(status="archived_present"),
        job_event_repo=FakeJobEventRepo(task_ref="bt-1"),
        adult_scan_dirs=(adult_dir,),
    )

    decision = service.inspect(
        normalized_content_id="censored:ssis-123",
        display_title="SSIS-123",
    )

    assert decision.should_warn is True
    assert decision.snapshot_status == "fresh"
    assert decision.evidence[0].kind == "local_path"
    assert "SSIS-123 sample.mp4" in decision.evidence[0].summary
```

- [ ] **Step 2: Run the focused service test and verify it fails**

Run: `.venv/bin/python -m pytest -q tests/test_adult_duplicate_memory.py -k prefers_exact_id_evidence`

Expected: `FAIL` because `AdultDuplicateMemoryService` and related decision types do not exist.

- [ ] **Step 3: Write the minimal service and exact-match scan path**

```python
@dataclass(frozen=True, slots=True)
class DuplicateEvidence:
    kind: str
    summary: str
    raw_value: str


@dataclass(frozen=True, slots=True)
class AdultDuplicateDecision:
    normalized_content_id: str
    display_title: str
    snapshot_status: str
    should_warn: bool
    degraded: bool
    warning_text: str
    evidence: tuple[DuplicateEvidence, ...]


class AdultDuplicateMemoryService:
    def __init__(
        self,
        *,
        snapshot_repo: AdultDuplicateMemorySnapshotRepo,
        adult_content_registry_repo: AdultContentRegistryRepo | None,
        job_event_repo: JobEventRepo | None,
        adult_scan_dirs: Sequence[Path],
    ) -> None:
        self._snapshot_repo = snapshot_repo
        self._adult_content_registry_repo = adult_content_registry_repo
        self._job_event_repo = job_event_repo
        self._adult_scan_dirs = tuple(path.expanduser() for path in adult_scan_dirs)

    def inspect(self, *, normalized_content_id: str, display_title: str) -> AdultDuplicateDecision:
        evidence: list[DuplicateEvidence] = []
        for scan_dir in self._adult_scan_dirs:
            for path in scan_dir.rglob("*"):
                if not path.is_file():
                    continue
                match = extract_exact_adult_content_match(path.name)
                if match is None or match.normalized_content_id != normalized_content_id:
                    continue
                evidence.append(
                    DuplicateEvidence(kind="local_path", summary=f"本地命中：{path}", raw_value=str(path))
                )

        registry_row = (
            self._adult_content_registry_repo.get_by_normalized_content_id(normalized_content_id)
            if self._adult_content_registry_repo is not None
            else None
        )
        if registry_row is not None:
            evidence.append(
                DuplicateEvidence(
                    kind="registry",
                    summary=f"历史状态：{registry_row.current_status}",
                    raw_value=registry_row.current_status,
                )
            )

        should_warn = bool(evidence)
        warning_text = "检测到该番号已有本地或历史命中；如需继续，请显式确认继续下载。" if should_warn else ""
        return AdultDuplicateDecision(
            normalized_content_id=normalized_content_id,
            display_title=display_title,
            snapshot_status="fresh" if should_warn else "fresh",
            should_warn=should_warn,
            degraded=False,
            warning_text=warning_text,
            evidence=tuple(evidence),
        )
```

- [ ] **Step 4: Re-run the focused service tests**

Run: `.venv/bin/python -m pytest -q tests/test_adult_duplicate_memory.py`

Expected: `PASS`, including exact-code hit and no false-positive title-only cases.

- [ ] **Step 5: Commit the service slice**

```bash
git add app/services/adult_duplicate_memory.py app/services/adult_content.py tests/test_adult_duplicate_memory.py
git commit -m "feat: add adult duplicate memory service"
```

### Task 3: Gate Pending Download Creation With Explicit Duplicate Override

**Files:**
- Create: `app/bot/private_chat_bt_duplicate_runtime.py`
- Modify: `app/services/add_to_downloader.py`
- Modify: `app/bot/private_chat_runtime.py`
- Modify: `app/bot/telegram_bot.py`
- Test: `tests/test_add_to_downloader.py`
- Test: `tests/test_private_chat_runtime.py`
- Test: `tests/test_telegram_bot.py`

- [ ] **Step 1: Write the failing guard and follow-up tests**

```python
def test_add_candidate_source_returns_duplicate_warning_before_pending_add(tmp_path: Path) -> None:
    service = build_add_service_with_duplicate_decision(
        AdultDuplicateDecision(
            normalized_content_id="censored:ssis-123",
            display_title="SSIS-123",
            snapshot_status="fresh",
            should_warn=True,
            degraded=False,
            warning_text="检测到旧记录",
            evidence=(DuplicateEvidence(kind="registry", summary="历史状态：archived_present", raw_value="archived_present"),),
        )
    )

    reply = _run(
        service.add_candidate_source(
            chat_id=1001,
            source="magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
            title="SSIS-123",
        )
    )

    assert "检测到旧记录" in reply
    assert "继续下载：发送 继续下载 SSIS-123" in reply
    assert "待确认：下载" not in reply


def test_private_chat_runtime_routes_duplicate_override_follow_up() -> None:
    runtime = build_private_chat_runtime_with_duplicate_override()

    reply = _run(runtime.dispatch_private_chat_text(chat_id=1001, user_id=2001, text="继续下载 SSIS-123"))

    assert "待确认：下载" in reply
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_add_to_downloader.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "duplicate_warning_before_pending_add or duplicate_override_follow_up"`

Expected: `FAIL` because there is no duplicate override stage or runtime handler yet.

- [ ] **Step 3: Write the minimal shared gate and follow-up runtime**

```python
BT_PENDING_STAGE_DUPLICATE_OVERRIDE = "duplicate_override"


async def add_candidate_source(self, *, chat_id: int, source: str, title: str, **kwargs: object) -> str:
    pending_add = build_pending_add_context(...)
    decision = self._adult_duplicate_memory_service.inspect(
        normalized_content_id=pending_add.adult_content_id,
        display_title=pending_add.adult_display_id or pending_add.title,
    )
    if decision.should_warn:
        self._bt_pending_repo.upsert(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_DUPLICATE_OVERRIDE,
            payload_json=json.dumps({"pending_add": pending_add_to_json(pending_add)}, ensure_ascii=False),
        )
        evidence_lines = "\n".join(f"- {item.summary}" for item in decision.evidence)
        return (
            f"{decision.warning_text}\n"
            f"{evidence_lines}\n"
            f"继续下载：发送 继续下载 {pending_add.adult_display_id or pending_add.title}\n"
            "取消：发送 cancel"
        )
    return await self._create_pending_add_reply(pending_add)


async def handle_bt_duplicate_override_follow_up(...) -> str:
    pending_state = pending_repo.get(chat_id)
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_DUPLICATE_OVERRIDE:
        return ADD_PENDING_STATE_UNAVAILABLE_TEXT
    payload = json.loads(pending_state.payload_json)
    pending_add = pending_add_from_json(payload["pending_add"])
    pending_repo.clear(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_DUPLICATE_OVERRIDE)
    return await add_service.create_pending_from_context(chat_id=chat_id, pending_add=pending_add)
```

- [ ] **Step 4: Re-run the focused guard tests**

Run: `.venv/bin/python -m pytest -q tests/test_add_to_downloader.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "duplicate_warning_before_pending_add or duplicate_override_follow_up"`

Expected: `PASS`

- [ ] **Step 5: Commit the shared gate slice**

```bash
git add app/services/add_to_downloader.py app/bot/private_chat_bt_duplicate_runtime.py app/bot/private_chat_runtime.py app/bot/telegram_bot.py tests/test_add_to_downloader.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py
git commit -m "feat: gate adult downloads with duplicate override"
```

### Task 4: Add Backfill And Inspect Tooling, Then Close With Focused Verification

**Files:**
- Create: `app/maintenance/adult_duplicate_memory_tools.py`
- Modify: `docs/STATUS.md`
- Modify: `docs/NEXT_STEP.md`
- Modify: `docs/TASKS.md`
- Test: `tests/test_adult_duplicate_memory_tools.py`

- [ ] **Step 1: Write the failing CLI-focused test**

```python
def test_adult_duplicate_memory_tools_inspect_prints_local_registry_and_event_hits(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    database = SqliteDatabase(str(tmp_path / "adult-duplicate.sqlite3"))
    database.initialize()
    seed_duplicate_snapshot(database, normalized_content_id="censored:ssis-123")

    exit_code = main(["inspect", "--db", str(tmp_path / "adult-duplicate.sqlite3"), "--content-id", "censored:ssis-123"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "censored:ssis-123" in output
    assert "local_path" in output
    assert "archived_present" in output
```

- [ ] **Step 2: Run the tooling test and verify it fails**

Run: `.venv/bin/python -m pytest -q tests/test_adult_duplicate_memory_tools.py -k inspect_prints_local_registry_and_event_hits`

Expected: `FAIL` because the maintenance tool does not exist yet.

- [ ] **Step 3: Write the minimal backfill/inspect tool**

```python
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="adult_duplicate_memory_tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--db", required=True)
    inspect_parser.add_argument("--content-id", required=True)

    backfill_parser = subparsers.add_parser("backfill")
    backfill_parser.add_argument("--db", required=True)

    args = parser.parse_args(argv)
    database = SqliteDatabase(args.db)
    database.initialize()
    repo = AdultDuplicateMemorySnapshotRepo(database)

    if args.command == "inspect":
        row = repo.get_snapshot(args.content_id)
        if row is None:
            print("not found")
            return 1
        print(row.normalized_content_id)
        print(row.snapshot_status)
        print(row.evidence_summary_json)
        return 0

    rebuilt = run_backfill(database=database)
    print(f"backfilled={rebuilt}")
    return 0
```

- [ ] **Step 4: Run the full duplicate-memory verification bundle**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_persistence_sqlite.py -k adult_duplicate_memory_snapshot && \
.venv/bin/python -m pytest -q tests/test_adult_duplicate_memory.py tests/test_adult_duplicate_memory_tools.py && \
.venv/bin/python -m pytest -q tests/test_add_to_downloader.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k duplicate && \
make quality && make verify-mainline && make verify-adult-bt-wedge && make lint
```

Expected:
- duplicate-memory focused tests all `PASS`
- `make quality` passes
- `make verify-mainline` passes
- `make verify-adult-bt-wedge` passes
- `make lint` passes

- [ ] **Step 5: Commit the operator tooling and truth sync**

```bash
git add app/maintenance/adult_duplicate_memory_tools.py docs/STATUS.md docs/NEXT_STEP.md docs/TASKS.md tests/test_adult_duplicate_memory_tools.py
git commit -m "feat: add adult duplicate memory operator tooling"
```
