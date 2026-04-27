from __future__ import annotations

from app.db.job_repo import JobRecord, JobRepo
from app.db.candidate_repo import CandidateMappingRepo
from app.db.download_monitor_repo import DownloadMonitorRecord, DownloadMonitorRepo, DownloadMonitorUpdate
from app.db.job_event_repo import JobEvent, JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.db.telegram_update_repo import TelegramUpdateRepo
from app.db.watchlist_repo import WatchlistItem, WatchlistRepo
