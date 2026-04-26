# Import pipeline redesign (v1)

> 目的：把 `app/services/import_to_library.py` 当前入口、分支密度和候选数据结构先固化成可复验基线，再进入真正的结构降本。
> 基线日期：2026-04-22

## 1. 入口路径清单

复现命令：

```bash
rg -n "\.import_by_task_ref\(|\.confirm_import_by_task_ref\(|cancel_pending_import\(|parse_import_query\(|parse_confirm_query\(" app
```

补充基线：

```bash
wc -l app/services/import_to_library.py
```

当前基线：

- `app/services/import_to_library.py` = `2242` 行
- 当前生产副作用入口共 `4` 条：手动 import、手动 confirm、手动 cancel、自动导入

| 调用文件 | 调用函数 | 进入 `import_to_library.py` 的入口 | 进入分支 |
| --- | --- | --- | --- |
| `app/bot/private_chat_import_runtime.py` | `handle_import_query()` | `parse_import_query()` -> `ImportToLibraryService.import_by_task_ref()` | 私聊收到 `import ...` / `导入 ...`，通过 `ACTION_IMPORT_TO_LIBRARY` 进入手动导入申请链 |
| `app/bot/private_chat_confirm_runtime.py` | `reply_confirm_import()` / `handle_confirm_query()` | `ImportToLibraryService.confirm_import_by_task_ref()` | 私聊收到 `confirm ...` / `确认 ...`，且 `jobs` 或 pending 路由判定当前待确认工作流属于 import |
| `app/bot/private_chat_frustration_runtime.py` | `_cancel_pending_import_for_frustration()` | `ImportToLibraryService.cancel_pending_import()` | 用户发送 frustration/reset，且当前最新 pending job 属于 import workflow |
| `app/services/post_download_auto_import.py` | `PostDownloadAutoImportService.run_for_record()` | 注入的 `auto_import_func` -> `ImportToLibraryService.import_by_task_ref()` | `download_monitor` 记录已完成、聊天身份有效、没有 import 终态事件、也没命中低质量自动跳过规则 |
| `app/main.py` | `build_application()` wiring | `lambda task_ref, chat_id, user_id: import_to_library_service.import_by_task_ref(...)` | 这里只负责把自动导入 service 接回 import 主入口，不额外加业务分支 |

解析辅助入口：

| 调用文件 | 调用函数 | 入口 | 作用 |
| --- | --- | --- | --- |
| `app/bot/private_chat_import_runtime.py` | `handle_import_query()` | `parse_import_query()` | 只负责把文本提成 `task_ref`，本身不触发副作用 |
| `app/bot/private_chat_runtime.py` | `_handle_tail_routes()` | `parse_confirm_query()` | 只判断文本是不是 confirm，再交给 confirm runtime 决定是否进入 import confirm |

测试入口说明：

- `tests/test_import_to_library.py`、`tests/test_persistence_sqlite.py`、`tests/test_telegram_bot.py` 等会直接 new `ImportToLibraryService(...)` 并调用 `import_by_task_ref()` / `confirm_import_by_task_ref()` / `cancel_pending_import()`；这些属于覆盖入口，不是生产路由入口。

## 2. 特殊分支 grep 计数

复现命令：

```bash
grep -c "if " app/services/import_to_library.py
grep -c "elif " app/services/import_to_library.py
grep -c "except " app/services/import_to_library.py
```

当前数值基线：

- `if ` = `236`
- `elif ` = `12`
- `except ` = `32`

主要分支英文标签分类：

| Label | 主要落点 | 当前分支在处理什么 |
| --- | --- | --- |
| `raw_bt_guard` | `import_by_task_ref()` / `_is_raw_bt_task()` | 阻断 `raw_bt` 资源误入媒体入库链 |
| `prepare_source_and_target` | `_prepare_import()` | 下载完成校验、源路径存在、目标根目录可建、目标冲突检查 |
| `approval_pending_write` | `_record_pending_approval()` / `_record_pending_job()` | 创建 approval pending、jobs pending 和对应事件 |
| `confirm_context_rebuild` | `confirm_import_by_task_ref()` / `_rebuild_confirm_context()` | 从 `jobs` + `approval_record` 重建 confirm 执行上下文 |
| `stale_or_not_pending` | `_find_version_stale_rejection_text()` / `_find_latest_import_target_path()` | 用 lease/executed_version 和历史 `import.succeeded` 判 stale / not pending |
| `execution_mode_copy_vs_hardlink` | `_resolve_execution_mode()` / `_execute_import()` | 在 hardlink / copy fallback / payload 恢复之间切换执行模式 |
| `approval_and_job_recovery` | `_record_import_approval()` / `_restore_pending_approval()` / `_claim_pending_job()` / `_restore_pending_job()` / `_mark_completed_job()` | confirm 期间的审批、抢占、回退、完结与 lease 维护 |
| `expiry_and_cancel` | `_handle_expired_pending_confirm()` / `_is_pending_approval_expired()` / `cancel_pending_import()` | pending 超时、用户取消、审批和 jobs 同步清理 |
| `file_transfer` | `_execute_import()` / `_hardlink_import()` / `_copy_import()` | 文件导入执行、`EXDEV` copy-fallback、目标存在、IO 失败 |
| `post_import_side_effects` | `_try_scrape_metadata()` / `_try_translate_subtitle()` / refresh block | metadata / subtitle / refresh 的后置动作 |
| `naming_truth_lookup` | `_resolve_normalized_naming_truth()` / `_resolve_metadata_title_year()` | 从 `job_event` 取命名真相，不足时回退到文件名解析 |
| `event_persistence_fail_closed` | `_record_event()` 及各类错误日志 helper | 事件、审批、jobs 查询/写入失败时 fail-closed 输出中文日志 |

结论：

- `236 / 12 / 32` 这个密度说明 `import_to_library.py` 现在不是单纯“大”，而是把“审批状态机 + 文件导入 + 后置 side-effect + 失败恢复”四类逻辑压在了同一文件里。
- 真正优先拆的不是 parser，也不是小工具函数，而是那些已经形成稳定边界的整段路径。

## 3. 候选数据结构草图

复现命令：

```bash
rg -n "PreparedImport|ImportExecutionResult|ImportTargetLookupResult|_prepare_import|_execute_import|_try_scrape_metadata|_try_translate_subtitle|_resolve_execution_mode|_record_pending_approval|_record_import_approval|_restore_pending_approval|_record_event" app/services/import_to_library.py
```

候选草图：

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class ImportIdentity:
    task_ref: str
    task_id: str
    task_hash: str
    chat_id: int | None
    user_id: int | None
    trigger: Literal["manual_import", "confirm_import", "auto_import", "cancel_pending"]


@dataclass(frozen=True, slots=True)
class ImportSourceSnapshot:
    name: str
    download_dir: Path
    source_path: Path
    percent_done: float
    raw_bt: bool


@dataclass(frozen=True, slots=True)
class ImportTargetPlan:
    library_root: Path
    naming_truth: str
    normalized_name: str
    target_path: Path
    execution_mode: Literal["hardlink", "copy"]
    resume_from_copy_fallback: bool = False


@dataclass(frozen=True, slots=True)
class ImportSideEffectPlan:
    metadata_title: str
    metadata_year: str
    should_scrape_metadata: bool
    should_translate_subtitle: bool
    should_refresh_server: bool


@dataclass(frozen=True, slots=True)
class ImportRequest:
    identity: ImportIdentity
    source: ImportSourceSnapshot
    target: ImportTargetPlan
    side_effects: ImportSideEffectPlan
    pending_lease_version: int | None = None


@dataclass(frozen=True, slots=True)
class ImportStepResult:
    reply_suffix: str = ""
    stop_pipeline: bool = False


class ImportStep(Protocol):
    async def run(self, request: ImportRequest) -> ImportStepResult: ...


class ImportStateStore(Protocol):
    def create_pending(self, request: ImportRequest) -> int: ...
    def approve(self, request: ImportRequest, lease_version: int) -> bool | None: ...
    def restore_pending(self, request: ImportRequest, lease_version: int) -> bool | None: ...
    def mark_executed(self, request: ImportRequest, lease_version: int) -> bool | None: ...
    def claim_job(self, request: ImportRequest, lease_owner: str) -> bool | None: ...
    def release_job(self, request: ImportRequest, lease_owner: str) -> None: ...
    def complete_job(self, request: ImportRequest, lease_owner: str) -> bool | None: ...


class ImportEventSink(Protocol):
    def record(self, request: ImportRequest, event_type: str, message: str, *, source_path: str = "", target_path: str = "") -> None: ...
```

推荐 pipeline 顺序：

1. `ImportQueryGateStep`
2. `ImportPrepareStep`
3. `ImportApprovalStep`
4. `ImportTransferStep`
5. `ImportMetadataStep`
6. `ImportSubtitleStep`
7. `ImportRefreshStep`
8. `ImportFinalizeStep`

按这个结构后，会自然消失的分支：

- `if self._scrape_metadata_func is None` / `if self._translate_subtitle_func is None` / `if self._refresh_media_server_func is None`
  因为 pipeline builder 直接决定某个 step 要不要装配，而不是在主文件里每次 `if/return`。
- `if execution_mode == IMPORT_EXECUTION_MODE_COPY`
  因为 `ImportTransferStep` 只接收已经定好的 `execution_mode`，hardlink/copy 不再在 confirm 主链里来回分叉。
- `if self._approval_repo is None` / `if self._job_repo is None`
  因为 `ImportStateStore` 可以在构造时就选 `SQLite` 或 `InMemory` 实现，业务主链不再关心 repo 有没有注入。
- `payload_json` 里的 copy-fallback 解析分支
  因为 `resume_from_copy_fallback` 可以先在 `ImportPrepareStep` 里解析成 typed field，后续 step 不再反复读 JSON。
- metadata 标题 / 年份 fallback 里的多层 `if`
  因为 `ImportSideEffectPlan` 预先把 `metadata_title` / `metadata_year` 算好，执行 step 只消费结果。

当前评估：

- **不撤回主线**。`post_import_side_effects` 已经是一条相对独立的后置链，只依赖 `task identity + target_path + optional hooks`，适合作为第一个真正落地的 pipeline step。
- 下一条最小实现建议：先把 `metadata / subtitle / refresh` 从 `import_to_library.py` 抽成独立 helper，主文件先降一段体积，再继续处理 approval / jobs 这条更高风险的状态机。
