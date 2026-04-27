# Current status (v514)

## Current mainline
- **质量硬化** 继续保持完成态；当前唯一主线仍是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮连续完成 10 个最小闭环：把 `downloader_route_lookup`、`private_chat_confirm_runtime`、`private_chat_cleanup_runtime`、`private_chat_frustration_runtime`、`private_chat_bt_read_only_runtime`、`raw_bt_destination_runtime`、`bt_tmdb_association_runtime`、`bt_pending_runtime`、`clients/feishu.py`、`clients/web_source.py` 的手写 ANSI 日志收口到共享 `emit_operational_log` 边界。
- 本轮同时修复下载器投递失败边界：`add_torrent_func` 抛出运行时 / HTTP 错误时，`confirm add` 重新返回明确失败文本并触发既有审批回退，不再把 downloader dispatch 异常泄出到调用方。
- 本轮 focused tests 已通过；`make quality`、`make verify-mainline` 已通过。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 通过；本轮 focused tests 已覆盖 downloader route lookup、确认/cleanup/frustration、BT read-only、raw BT、BT TMDB、BT pending、Feishu client 和 BT source 路径。
- `tests/test_downloader_route_lookup.py`、`tests/test_private_chat_confirm_runtime.py`、`tests/test_private_chat_cleanup_runtime.py`、`tests/test_private_chat_frustration_runtime.py`、`tests/test_private_chat_bt_read_only_runtime.py`、`tests/test_private_chat_raw_bt_destination_runtime.py`、`tests/test_private_chat_bt_tmdb_runtime.py`、`tests/test_private_chat_bt_processing_runtime.py`、`tests/test_feishu_client.py`、`tests/test_bt_sources.py` 通过。
- `make quality` 通过（`27 passed in 0.13s`），`make verify-mainline` 通过。
- 下一轮继续质量债时，优先从剩余 broad `except Exception` 中区分“外部服务隔离”与“repo/SQLite 持久化边界”，或继续收口日志打印边界 / `main()` DI；不要切成人 BT 新功能。

## Latest verification
- `tests/test_downloader_route_lookup.py`、`tests/test_private_chat_confirm_runtime.py`、`tests/test_private_chat_cleanup_runtime.py`、`tests/test_private_chat_frustration_runtime.py`、`tests/test_private_chat_bt_read_only_runtime.py`、`tests/test_private_chat_raw_bt_destination_runtime.py`、`tests/test_private_chat_bt_tmdb_runtime.py`、`tests/test_private_chat_bt_processing_runtime.py`、`tests/test_feishu_client.py`、`tests/test_bt_sources.py` 通过。
- `make quality` 通过（`27 passed, 0 skipped`）。
- `make verify-mainline` 通过。

## Current biggest risk
- 剩余 broad `except Exception` 中仍有一部分是外部服务降级、网络/LLM/TMDB/search wrapper、后台 task loop 或 webhook 边界；不能机械替换。
- 继续施工时应优先挑有 focused tests 的 repo/SQLite 持久化边界，或先补最小测试再收口。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线是质量债硬化。优先从剩余 broad except、日志打印边界或 `main()` DI 里挑一个最小闭环；不要重建已收掉的小 support 文件，不要切成人 BT 新功能，不改协议或 SQLite 真相边界。
```
