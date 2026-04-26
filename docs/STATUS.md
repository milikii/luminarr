# Current status (v469)

## Current mainline

- **质量硬化** 当前保持完成态，不回退。
- 当前默认分支主线已从“刮削系统基础收口”切到 **成人 BT 专线基础收口**；direct magnet 入口仍保留“观影 PT 链 / BT 成人链”问询，不自动假定成人链。
- 成人 BT 当前新真相已落地：
  - `adult_content_registry` 已记录 `pending / downloading / archived_present / archived_deleted`
  - BT 预览 / 批量预览 / 待确认文本已能提示历史状态
  - 成人 BT 下载完成后可进入归档，统一保留窗口到期后可清理下载器任务与源资源
- 三座大山保持完成态：`app/services/search_media.py` `568` 行，`add_to_downloader.py` `574` 行，`import_to_library.py` `585` 行。
- BT 来源适配当前保持：
  - 成人站点优先：`tokyotosho` / `sukebei(offkab)` / `javbus`
  - `Prowlarr` 成人 PT 作为补充来源
  - `javlibrary` helper 仍待补成只读识别补全

## Current health

- 当前变更只触碰 BT/下载完成 follow-up 相关边界，没有改 movie-first PT / import / metadata 主链协议。
- 当前最大风险不是主链是否成立，而是：
  - 成人归档 sidecar 与现有 auto-import sidecar 的共存是否还有遗漏红灯
  - direct magnet 问询边界与成人 BT 新语义是否会在后续文档或小改里被误放宽

## Latest verification

- `make quality`：当前轮已重跑通过，文档一致性 gate 重新回绿
- `make verify-mainline`：当前轮已重跑通过，shared-runtime / channel / BT follow-up focused 回归未见业务红灯
- `make test`：`1761 passed, 2 skipped`
- `.venv/bin/python -m pyflakes`：
  - 成人内容解析 / 历史账本 / 成人归档 / 新站点模板相关文件全部通过
- focused pytest：
  - `tests/test_adult_content.py`
  - `tests/test_adult_archive_service.py`
  - `tests/test_search_media.py`
  - `tests/test_bt_sources.py`
  - `tests/test_pure_bt.py`
  - `tests/test_qbittorrent_client.py`
  - `tests/test_transmission_client.py`
  - `tests/test_add_execution_follow_up.py`
  - `tests/test_config.py`
  - 合计 `243 passed`
- 运行时 focused：
  - `tests/test_add_to_downloader.py tests/test_download_follow_up_runtime.py tests/test_get_download_status.py -k "download_monitor or auto_import or adult or confirm_add_by_task_ref_registers_download_monitor_truth or post_download_auto_import_scheduler"`：`30 passed`
  - `tests/test_persistence_sqlite.py -k "download_monitor or adult_content_registry or sqlite or job_repo_rejects_missing_identity_for_state_transitions"`：`111 passed`

## Current biggest risk

- 当前最大不确定性已经从“成人 BT 能否接进来”转成“下一步是先补 `javlibrary` helper，还是先做更大 gate / real smoke 来压成人归档 sidecar 风险”。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

保持当前成人 BT 主线，并继续让 direct magnet 先问链路，不自动改成成人 BT 直投。
```
