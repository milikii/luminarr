# Current status (v520)

## Current mainline
- **质量硬化** 继续保持完成态；当前唯一主线仍是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮继续收口 10 个异常边界：`import_post_processing` 的 metadata/subtitle/refresh 只吞掉明确 `RuntimeError`，`subtitle_translation_support` 的模型翻译失败只吞掉明确 `RuntimeError`，`refresh_media_server` 只吞掉明确 `httpx.HTTPError`，`search_recovery_runtime` 与 `status_follow_up` 只对明确 `RuntimeError` 进入恢复或降级，`private_chat_bt_read_only_runtime` / `raw_bt_destination_runtime` / `bt_tmdb_association_runtime` 的外部查询失败只吞掉明确 `httpx.HTTPError` / `ValueError`。
- 本轮同时补了 import post-processing、search recovery、下载状态 auto-import follow-up、BT 只读探索、raw BT 目标目录、BT TMDB 关联的 focused regression，把相关网络失败模拟统一收成真实 `httpx.ConnectError`，并补了“非预期 `ValueError` 继续上抛”的守卫测试。
- 本轮只改异常捕获类型和测试输入，不改协议、SQLite schema、下载/导入/刷新/BT follow-up 语义，也没有引入新增用户可感知功能。
- 本轮 focused tests 已通过；`make quality`、`make verify-mainline` 均重新通过。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 通过；本轮 focused tests 覆盖 import post-processing、refresh media server、subtitle translator、下载状态 auto-import follow-up、BT 只读 / raw BT / BT TMDB follow-up 与 search recovery。
- 本轮未触发真实 downloader / refresh 协议行为变化；改动为异常边界收窄，并由 focused tests 与 mainline gate 覆盖。
- `make quality` 通过（`27 passed, 0 skipped`），`make verify-mainline` 通过。
- 下一轮继续质量债时，优先从剩余 broad `except Exception` 中区分“外部服务隔离”与“repo/SQLite 持久化边界”，或继续收口剩余日志打印边界 / `main()` DI；不要切成人 BT 新功能。

## Latest verification
- `tests/test_refresh_media_server.py tests/test_private_chat_bt_read_only_runtime.py tests/test_private_chat_bt_tmdb_runtime.py tests/test_private_chat_raw_bt_destination_runtime.py tests/test_subtitle_translator.py tests/test_import_to_library.py tests/test_search_recovery_runtime.py tests/test_get_download_status.py` 通过（`266 passed`）。
- `make quality` 通过（`27 passed, 0 skipped`）。
- `make verify-mainline` 通过。

## Current biggest risk
- 剩余 broad `except Exception` 中仍有一部分是外部服务降级、LLM、后台 task loop、SDK 长连接或 webhook 边界；不能机械替换。
- 渠道入口、维护脚本和部分后处理隔离层仍有手写 ANSI 日志或宽捕获；继续施工时应优先挑有 focused tests 的服务层或明确本地 I/O/repo/SQLite 边界，避免把外部 webhook/SDK loop 隔离边界误收窄。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线是质量债硬化。优先从剩余 broad except、日志打印边界或 `main()` DI 里挑一个最小闭环；不要重建已收掉的小 support 文件，不要切成人 BT 新功能，不改协议或 SQLite 真相边界。
```
