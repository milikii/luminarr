# Current status (v515)

## Current mainline
- **质量硬化** 继续保持完成态；当前唯一主线仍是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮连续完成 10 个最小闭环：把 `app/main.py`、`telegram_update_runtime`、`telegram_delivery_runtime`、`channel_identity`、`download_follow_up_runtime`、`metadata_scraper`、`subtitle_translation_support`、`manage_watchlist`、`manage_bt_subscription`、`cleanup_correlation_lookup` 的剩余手写/间接 ANSI 日志继续收口到共享 `emit_operational_log` 边界。
- 本轮同时修复两个只读/cleanup 失败边界：下载状态路由读取异常会包装成明确 `DownloaderRouteLookupError`；cleanup correlation 的 `job_event` 查询运行时错误会进入既有查询失败边界，不再跨渠道泄出异常。
- 本轮 focused tests 已通过；`make quality`、`make verify-mainline` 已通过。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 通过；本轮 focused tests 已覆盖 main/downloader route、Telegram update/delivery、跨渠道身份、download follow-up、metadata/subtitle、watchlist/BT subscription、cleanup correlation/cross-channel 路径。
- `tests/test_main.py`、`tests/test_downloader_route_lookup.py`、`tests/test_telegram_runtime_adapter.py`、`tests/test_telegram_delivery_runtime.py`、`tests/test_feishu_adapter.py`、`tests/test_wecom_adapter.py`、`tests/test_personal_wechat_text.py`、`tests/test_download_follow_up_runtime.py`、`tests/test_metadata_scraper.py`、`tests/test_subtitle_translator.py`、`tests/test_manage_watchlist.py`、`tests/test_manage_bt_subscription.py`、`tests/test_bt_subscription_last_seen_support.py`、`tests/test_bt_subscription_scan_support.py`、`tests/test_bt_subscription_scheduler_support.py`、`tests/test_cleanup_downloaded_source.py`、`tests/test_cleanup_cross_channel_smoke.py` 通过。
- `make quality` 通过（`27 passed in 0.13s`），`make verify-mainline` 通过。
- 下一轮继续质量债时，优先从剩余 broad `except Exception` 中区分“外部服务隔离”与“repo/SQLite 持久化边界”，或继续收口日志打印边界 / `main()` DI；不要切成人 BT 新功能。

## Latest verification
- `tests/test_main.py tests/test_downloader_route_lookup.py` 通过。
- `tests/test_telegram_runtime_adapter.py`、`tests/test_telegram_delivery_runtime.py` 通过。
- `tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_personal_wechat_text.py` 通过。
- `tests/test_download_follow_up_runtime.py`、`tests/test_metadata_scraper.py`、`tests/test_subtitle_translator.py` 通过。
- `tests/test_manage_watchlist.py`、`tests/test_manage_bt_subscription.py tests/test_bt_subscription_last_seen_support.py tests/test_bt_subscription_scan_support.py tests/test_bt_subscription_scheduler_support.py` 通过。
- `tests/test_cleanup_downloaded_source.py tests/test_cleanup_cross_channel_smoke.py` 通过（`428 passed`）。
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
