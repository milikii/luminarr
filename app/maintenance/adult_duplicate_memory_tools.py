from __future__ import annotations

from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path

from app.db.adult_content_registry_repo import AdultContentRegistryRepo
from app.db.adult_duplicate_memory_snapshot_repo import AdultDuplicateMemorySnapshotRepo
from app.db.job_event_repo import JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.services.adult_duplicate_memory import AdultDuplicateMemoryService


def run_backfill(*, database: SqliteDatabase, scan_dirs: Sequence[Path]) -> int:
    registry_repo = AdultContentRegistryRepo(database)
    snapshot_repo = AdultDuplicateMemorySnapshotRepo(database)
    service = AdultDuplicateMemoryService(
        snapshot_repo=snapshot_repo,
        adult_content_registry_repo=registry_repo,
        job_event_repo=JobEventRepo(database),
        adult_scan_dirs=scan_dirs,
    )

    rebuilt = 0
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT normalized_content_id, display_title
            FROM adult_content_registry
            ORDER BY normalized_content_id ASC
            """
        ).fetchall()
    for row in rows:
        normalized_content_id = str(row["normalized_content_id"]).strip().lower()
        if not normalized_content_id:
            continue
        display_title = str(row["display_title"]).strip() or normalized_content_id
        service.inspect(
            normalized_content_id=normalized_content_id,
            display_title=display_title,
        )
        rebuilt += 1
    return rebuilt


def build_argument_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="adult_duplicate_memory_tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--db", required=True)
    inspect_parser.add_argument("--content-id", required=True)

    backfill_parser = subparsers.add_parser("backfill")
    backfill_parser.add_argument("--db", required=True)
    backfill_parser.add_argument("--scan-dir", action="append", default=[])

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    database = SqliteDatabase(str(args.db))
    database.initialize()

    if args.command == "inspect":
        repo = AdultDuplicateMemorySnapshotRepo(database)
        row = repo.get_snapshot(args.content_id)
        if row is None:
            print("not found")
            return 1
        print(row.normalized_content_id)
        print(row.snapshot_status)
        print(row.evidence_summary_json)
        return 0

    scan_dirs = tuple(Path(item).expanduser() for item in args.scan_dir)
    rebuilt = run_backfill(database=database, scan_dirs=scan_dirs)
    print(f"backfilled={rebuilt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
