from __future__ import annotations

import sqlite3

from app.clients.transmission import TransmissionTaskStatus
from app.db.download_monitor_repo import DownloadMonitorPersistenceError, DownloadMonitorRepo
from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.services.post_download_auto_import import AutoImportStateUnavailableError, PostDownloadAutoImportService

STATUS_OBSERVATION_WARNING_TEXT = "注意：下载状态观察落盘失败，自动导入跟进可能未推进，请稍后重试。"
STATUS_COMPLETION_EVENT_WARNING_TEXT = "注意：下载完成观察事件落盘失败，后续恢复可能缺少这次完成记录，请稍后重试。"
STATUS_AUTO_IMPORT_STATE_UNAVAILABLE_TEXT = "注意：自动导入状态读取失败，本次状态查询未附带后续处理结果，请稍后重试。"
STATUS_AUTO_IMPORT_WARNING_TEXT = "注意：自动导入跟进失败，本次状态查询未附带后续处理结果，请稍后重试。"
DOWNLOAD_MONITOR_STATUS_RESULT_MISSING_REASON = "download monitor status result missing"
DOWNLOAD_MONITOR_OBSERVED_RECORD_MISSING_REASON = "download monitor observed record missing"
DOWNLOAD_MONITOR_STATUS_UPSERT_RESULT_MISSING_REASON = "download monitor state missing after status upsert"
DOWNLOAD_MONITOR_COMPLETION_FLAG_MISSING_REASON = "download monitor completion flag missing"
DOWNLOAD_COMPLETION_EVENT_RESULT_MISSING_REASON = "job_event missing after append"


class StatusFollowUpStateError(RuntimeError):
    pass


class StatusFollowUpRecorder:
    def __init__(
        self,
        *,
        download_monitor_repo: DownloadMonitorRepo | None,
        job_event_repo: JobEventRepo | None,
        post_download_auto_import_service: PostDownloadAutoImportService | None,
    ) -> None:
        self._download_monitor_repo = download_monitor_repo
        self._job_event_repo = job_event_repo
        self._post_download_auto_import_service = post_download_auto_import_service

    async def record(self, *, task_ref: str, task_status: TransmissionTaskStatus) -> str | None:
        if self._download_monitor_repo is None:
            return None
        try:
            update = self._download_monitor_repo.record_status(task_status)
            if update is None:
                raise StatusFollowUpStateError(DOWNLOAD_MONITOR_STATUS_RESULT_MISSING_REASON)
            if getattr(update, "record", None) is None:
                raise StatusFollowUpStateError(DOWNLOAD_MONITOR_OBSERVED_RECORD_MISSING_REASON)
            newly_completed = getattr(update, "newly_completed", None)
            if not isinstance(newly_completed, bool):
                raise StatusFollowUpStateError(DOWNLOAD_MONITOR_COMPLETION_FLAG_MISSING_REASON)
        except (DownloadMonitorPersistenceError, sqlite3.Error, StatusFollowUpStateError) as error:
            if str(error) in {
                DOWNLOAD_MONITOR_STATUS_RESULT_MISSING_REASON,
                DOWNLOAD_MONITOR_OBSERVED_RECORD_MISSING_REASON,
                DOWNLOAD_MONITOR_STATUS_UPSERT_RESULT_MISSING_REASON,
            }:
                _log_download_monitor_observation_result_missing(
                    task_ref=task_ref,
                    task_status=task_status,
                    reason=str(error),
                )
            elif _is_download_monitor_observation_row_corrupted_error(error):
                _log_download_monitor_observation_row_corrupted(
                    task_ref=task_ref,
                    task_status=task_status,
                    reason=str(error),
                )
            elif str(error) == DOWNLOAD_MONITOR_COMPLETION_FLAG_MISSING_REASON:
                _log_download_monitor_completion_flag_missing(
                    task_ref=task_ref,
                    task_status=task_status,
                    reason=str(error),
                )
            else:
                _log_download_monitor_observation_failed(task_ref=task_ref, task_status=task_status, reason=str(error))
            return STATUS_OBSERVATION_WARNING_TEXT
        follow_up_parts: list[str] = []
        if newly_completed and self._job_event_repo is not None:
            try:
                self._job_event_repo.append_event(
                    task_ref=task_ref,
                    task_id=task_status.task_id,
                    task_hash=task_status.task_hash,
                    event_type="downloader.completed_observed",
                    message=task_status.name,
                )
            except (JobEventPersistenceError, sqlite3.Error) as error:
                if str(error) == DOWNLOAD_COMPLETION_EVENT_RESULT_MISSING_REASON:
                    _log_download_completion_event_result_missing(
                        task_ref=task_ref,
                        task_status=task_status,
                        reason=str(error),
                    )
                elif _is_completion_event_row_corrupted_error(error):
                    _log_download_completion_event_row_corrupted(
                        task_ref=task_ref,
                        task_status=task_status,
                        reason=str(error),
                    )
                else:
                    _log_download_completion_event_append_failed(
                        task_ref=task_ref,
                        task_status=task_status,
                        reason=str(error),
                    )
                follow_up_parts.append(STATUS_COMPLETION_EVENT_WARNING_TEXT)
        if self._post_download_auto_import_service is None:
            if not follow_up_parts:
                return None
            return "\n\n".join(follow_up_parts)
        try:
            auto_import_text = await self._post_download_auto_import_service.run_for_record(update.record)
        except AutoImportStateUnavailableError as error:
            _log_status_auto_import_state_unavailable(
                task_ref=task_ref,
                task_status=task_status,
                reason=str(error),
            )
            auto_import_text = STATUS_AUTO_IMPORT_STATE_UNAVAILABLE_TEXT
        except Exception as error:
            _log_status_auto_import_follow_up_failed(
                task_ref=task_ref,
                task_status=task_status,
                reason=str(error),
            )
            auto_import_text = STATUS_AUTO_IMPORT_WARNING_TEXT
        if auto_import_text:
            follow_up_parts.append(auto_import_text)
        if not follow_up_parts:
            return None
        return "\n\n".join(follow_up_parts)


def _log_download_monitor_observation_failed(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    print(
        f"\033[31m[下载状态观察落盘失败]\033[0m task_ref={task_ref} task_id={task_status.task_id} "
        f"task_hash={task_status.task_hash} 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite/download_monitor 表写入是否正常；"
        "当前请求仍会返回下载状态文本，但下载完成观察和后续自动导入可能不会推进。",
        flush=True,
    )


def _log_download_monitor_observation_result_missing(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    print(
        f"\033[31m[下载状态观察结果缺失]\033[0m task_ref={task_ref} task_id={task_status.task_id} "
        f"task_hash={task_status.task_hash} 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 download_monitor 返回是否仍带有完整 update 和 record；"
        "当前请求仍会返回下载状态文本，但这次完成观察和后续自动导入不会继续推进。",
        flush=True,
    )


def _log_download_monitor_completion_flag_missing(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    print(
        f"\033[31m[下载状态观察完成标记缺失]\033[0m task_ref={task_ref} task_id={task_status.task_id} "
        f"task_hash={task_status.task_hash} 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 download_monitor 更新结果是否仍带有完整的 newly_completed 真相；"
        "当前请求仍会返回下载状态文本，但不会把这次完成观察继续推进到后续自动导入。",
        flush=True,
    )


def _log_download_monitor_observation_row_corrupted(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    print(
        f"\033[31m[下载状态观察记录损坏]\033[0m task_ref={task_ref} task_id={task_status.task_id} "
        f"task_hash={task_status.task_hash} 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 download_monitor 读回记录里的 task_id / task_hash / status_code / percent_done 等真相字段是否仍然完整；"
        "当前请求仍会返回下载状态文本，但这次完成观察和后续自动导入不会继续推进。",
        flush=True,
    )


def _log_download_completion_event_result_missing(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    print(
        f"\033[31m[下载完成观察事件结果缺失]\033[0m task_ref={task_ref} task_id={task_status.task_id} "
        f"task_hash={task_status.task_hash} event_type=downloader.completed_observed 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 job_event 写入后回读是否仍能拿到刚追加的完成观察事件；"
        "当前请求仍会返回下载状态文本，但这次完成观察事件真相还没有确认落稳。",
        flush=True,
    )


def _log_download_completion_event_row_corrupted(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    print(
        f"\033[31m[下载完成观察事件记录损坏]\033[0m task_ref={task_ref} task_id={task_status.task_id} "
        f"task_hash={task_status.task_hash} event_type=downloader.completed_observed 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 job_event 完成观察记录里的 task_ref / event_type 等字段是否仍是完整真相；"
        "当前请求仍会返回下载状态文本，但这次完成观察事件不会当成已稳定落盘。",
        flush=True,
    )


def _log_download_completion_event_append_failed(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    print(
        f"\033[31m[下载完成观察事件落盘失败]\033[0m task_ref={task_ref} task_id={task_status.task_id} "
        f"task_hash={task_status.task_hash} event_type=downloader.completed_observed 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite/job_event 表写入是否正常；"
        "当前请求仍会返回下载状态文本，但这次完成观察事件可能没有落盘。",
        flush=True,
    )


def _log_status_auto_import_state_unavailable(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    print(
        f"\033[31m[下载状态自动导入状态读取失败]\033[0m task_ref={task_ref} task_id={task_status.task_id} "
        f"task_hash={task_status.task_hash} 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite/download_monitor、job_event 和自动导入审批链路是否正常；"
        "当前请求仍会返回下载状态文本，但不会附带这次自动导入 follow-up。",
        flush=True,
    )


def _log_status_auto_import_follow_up_failed(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    print(
        f"\033[31m[下载状态自动导入跟进失败]\033[0m task_ref={task_ref} task_id={task_status.task_id} "
        f"task_hash={task_status.task_hash} 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查自动导入后半段依赖、SQLite 和导入审批链路；"
        "当前请求仍会返回下载状态文本，但不会附带这次自动导入 follow-up。",
        flush=True,
    )


def _is_download_monitor_observation_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, DownloadMonitorPersistenceError) and str(error).endswith("corrupted after read")


def _is_completion_event_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobEventPersistenceError) and str(error).endswith("corrupted after read")
