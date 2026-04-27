# Current status (v508)

## Current mainline
- **质量硬化** 继续保持完成态；当前唯一主线仍是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮按文档连续完成 10 个最小闭环：下载器路由、导入源查询、cleanup 事件与 PT seed window、命名规则解析、媒体服务器 refresh 配置日志、成人归档/保留期清理持久化状态不可用边界，以及成人归档状态不可用 follow-up 覆盖。
- 这些路径不再吞泛 `Exception`，只兜明确的 repo persistence 异常、`sqlite3.Error`、下载器/HTTP 查询异常或规则文件格式异常；外部搜索、TMDB/网络、后台 loop、webhook 的隔离性宽捕获未机械替换。
- 默认分支协议、SQLite schema、下载/导入/审批语义未变化；本轮主要是异常边界和测试模拟同步。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 通过；本轮 focused tests 覆盖 downloader route、import prepare、cleanup event/seed window、media name rules、main refresh DI、adult archive 与 auto-import adult follow-up。
- `make quality` 通过，`make verify-mainline` 通过。
- 下一轮继续质量债时，优先从剩余 broad `except Exception` 中区分“外部服务隔离”与“repo/SQLite 持久化边界”，或继续收口日志打印边界 / `main()` DI；不要切成人 BT 新功能。

## Latest verification
- `tests/test_main.py -k downloader_name_for_task`：`6 passed, 19 deselected`
- `tests/test_import_to_library.py -k "prepare_import_logs_query_failure or prepare_import_propagates_unexpected_query_failure"`：`2 passed, 148 deselected`
- `tests/test_cleanup_downloaded_source.py -k "event_append_failure"`：`3 passed, 47 deselected`
- `tests/test_cleanup_downloaded_source.py -k "pt_seed_window or event_append_failure or missing_appended_event_result"`：`8 passed, 44 deselected`
- `tests/test_media_name_parser.py -k "naming_rules"`：`3 passed, 14 deselected`
- `tests/test_main.py -k build_refresh_media_server_func`：`6 passed, 19 deselected`
- `tests/test_adult_archive_service.py`：`3 passed`
- `tests/test_adult_archive_service.py tests/test_get_download_status.py -k "adult_archive_service or adult_task"`：`6 passed, 43 deselected`
- `tests/test_get_download_status.py -k "adult_archive_state_is_unavailable or adult_task"`：`3 passed, 43 deselected`
- `tests/test_config.py`：`39 passed, 0 skipped`
- `make quality`：通过（`27 passed`）
- `make verify-mainline`：通过

## Current biggest risk
- 剩余 broad `except Exception` 中仍有一部分是外部服务降级、网络/LLM/TMDB/search wrapper、后台 task loop 或 webhook 边界；不能机械替换。
- 继续施工时应优先挑有 focused tests 的 repo/SQLite 持久化边界，或先补最小测试再收口。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线是质量债硬化。优先从剩余 broad except、日志打印边界或 `main()` DI 里挑一个最小闭环；不要重建已收掉的小 support 文件，不要切成人 BT 新功能，不改协议或 SQLite 真相边界。
```
