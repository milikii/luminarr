# Current status (v516)

## Current mainline
- **质量硬化** 继续保持完成态；当前唯一主线仍是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮连续完成 10 个最小闭环：把 `auto_import_batch`、`search_request_context`、`media_name_parser`、`bt_candidate_scorer`、`import_to_library`、`import_transfer_execution`、`post_download_auto_import`、`cleanup_downloaded_source`、`import_job_state`、`import_approval_state` 的剩余手写 ANSI 日志继续收口到共享 `emit_operational_log` 边界。
- 本轮又把 Feishu 入站边界收口到 **SDK 长连接 only**：删除了 Feishu webhook server / webhook 装配 / webhook 专属测试与配置入口，只保留 SDK 事件解析和 reply 链路。
- 本轮只改日志出口与可读诊断文本组织，不改协议、SQLite schema、下载/导入/刷新语义，也没有引入新增用户可感知功能。
- 本轮 focused tests 已通过；`make quality`、`make verify-mainline` 仍保持通过态，当前这轮变更还没重新跑全量 gate。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 通过；本轮 focused tests 覆盖自动导入候选、搜索请求、命名规则、BT 评分、导入审批/任务/执行、post-download auto import、cleanup 执行日志路径。
- 本轮未触发真实 downloader / refresh 协议行为变化；导入相关改动为日志出口替换，并由本地文件导入 focused tests 与 mainline gate 覆盖。
- `make quality` 仍保持通过态（上轮 `27 passed in 0.13s`），`make verify-mainline` 仍保持通过态；本轮新变更已通过 Feishu / config / personal WeChat / cleanup / main focused tests。
- 下一轮继续质量债时，优先从剩余 broad `except Exception` 中区分“外部服务隔离”与“repo/SQLite 持久化边界”，或继续收口剩余日志打印边界 / `main()` DI；不要切成人 BT 新功能。

## Latest verification
- `tests/test_get_download_status.py -k "completed_list"` 通过（`3 passed`）。
- `tests/test_search_media.py -k "tmdb or search"` 通过（`185 passed`）。
- `tests/test_media_name_parser.py` 通过（`17 passed`）。
- `tests/test_bt_candidate_scorer.py` 通过（`31 passed`）。
- `tests/test_import_to_library.py -k "expired or timeout or cancel_pending"` 通过（`19 passed`）。
- `tests/test_import_to_library.py -k "target_exists or hardlink or copy or fallback or payload or cleanup"` 通过（`18 passed`）。
- `tests/test_get_download_status.py -k "post_download_auto_import_run_for_record and (invalid_chat_identity or adult_registry or adult_archive)"` 通过（`4 passed`）。
- `tests/test_cleanup_downloaded_source.py tests/test_cleanup_cross_channel_smoke.py` 通过（`428 passed`）。
- `tests/test_import_to_library.py -k "job or lease or completed"` 通过（`41 passed`）。
- `tests/test_import_to_library.py -k "approval or lease or target or stale or expired or restore"` 通过（`71 passed`）。
- `make quality` 通过（`27 passed, 0 skipped`）。
- `make verify-mainline` 通过。

## Current biggest risk
- 剩余 broad `except Exception` 中仍有一部分是外部服务降级、网络/LLM/TMDB/search wrapper、后台 task loop 或 webhook 边界；不能机械替换。
- 渠道入口和维护脚本仍有手写 ANSI 日志；继续施工时应优先挑有 focused tests 的服务层或 repo/SQLite 边界，避免把外部 webhook/SDK loop 隔离边界误收窄。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线是质量债硬化。优先从剩余 broad except、日志打印边界或 `main()` DI 里挑一个最小闭环；不要重建已收掉的小 support 文件，不要切成人 BT 新功能，不改协议或 SQLite 真相边界。
```
