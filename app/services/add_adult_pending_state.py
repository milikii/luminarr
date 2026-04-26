from __future__ import annotations

from app.db.adult_content_registry_repo import AdultContentRegistryRepo
from app.services.add_pending_context import PendingAddContext


class AddAdultPendingState:
    def __init__(self, adult_content_registry_repo: AdultContentRegistryRepo | None) -> None:
        self._adult_content_registry_repo = adult_content_registry_repo

    def record_pending(self, *, pending_add: PendingAddContext) -> None:
        if self._adult_content_registry_repo is None:
            return
        if not pending_add.adult_content_id:
            return
        try:
            self._adult_content_registry_repo.upsert_pending(
                normalized_content_id=pending_add.adult_content_id,
                content_id_kind=pending_add.adult_content_kind or pending_add.adult_archive_category or "adult",
                archive_category=pending_add.adult_archive_category or "other_adult",
                display_title=pending_add.adult_display_id or pending_add.title,
                latest_source_site=pending_add.source_site,
                task_ref=pending_add.task_ref,
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                downloader_name=pending_add.downloader_name,
            )
        except Exception as error:
            print(
                f"\033[31m[成人资源待确认登记失败]\033[0m content_id={pending_add.adult_content_id} "
                f"task_ref={pending_add.task_ref} task_id={pending_add.task_id} task_hash={pending_add.task_hash} 错误={error}\n"
                "\033[33m[处理建议]\033[0m 检查 adult_content_registry 表写入是否正常；当前下载待确认已创建，但历史提醒可能不会及时更新。",
                flush=True,
            )
