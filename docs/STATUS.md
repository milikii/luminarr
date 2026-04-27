# Current status (v517)

## Current mainline
- **质量硬化** 继续保持完成态；当前唯一主线仍是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮继续完成异常边界与日志边界收口：`subtitle_translation_support` 的本地字幕读写、模型响应 JSON、metadata JSON 读取不再用泛 `Exception`；`metadata_scraper` 的 metadata/NFO/图片本地产物写入只捕获明确 I/O/编码异常。
- 本轮把 `wecom_adapter` callback 校验、解密、请求体和运行时失败的手写 ANSI 日志统一到 shared `emit_operational_log` 边界。
- 本轮只改异常捕获类型和日志出口，不改协议、SQLite schema、下载/导入/刷新语义，也没有引入新增用户可感知功能。
- 本轮 focused tests 已通过；`make quality`、`make verify-mainline` 均重新通过。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 通过；本轮 focused tests 覆盖字幕翻译、metadata 刮削、导入后处理和 WeCom callback 路由。
- 本轮未触发真实 downloader / refresh 协议行为变化；导入后处理相关改动为本地异常边界收窄，并由 focused tests 与 mainline gate 覆盖。
- `make quality` 通过（`27 passed, 0 skipped`），`make verify-mainline` 通过。
- 下一轮继续质量债时，优先从剩余 broad `except Exception` 中区分“外部服务隔离”与“repo/SQLite 持久化边界”，或继续收口剩余日志打印边界 / `main()` DI；不要切成人 BT 新功能。

## Latest verification
- `tests/test_subtitle_translator.py` 通过（`38 passed`）。
- `tests/test_metadata_scraper.py` 通过（`11 passed`）。
- `tests/test_subtitle_translator.py tests/test_metadata_scraper.py tests/test_import_to_library.py -k "metadata or subtitle or refresh"` 通过（`64 passed, 135 deselected`）。
- `tests/test_wecom_adapter.py` 通过（`33 passed`）。
- `make quality` 通过（`27 passed, 0 skipped`）。
- `make verify-mainline` 通过。

## Current biggest risk
- 剩余 broad `except Exception` 中仍有一部分是外部服务降级、网络/LLM/TMDB/search wrapper、后台 task loop 或 webhook 边界；不能机械替换。
- 渠道入口、维护脚本和部分后处理隔离层仍有手写 ANSI 日志或宽捕获；继续施工时应优先挑有 focused tests 的服务层或明确本地 I/O/repo/SQLite 边界，避免把外部 webhook/SDK loop 隔离边界误收窄。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线是质量债硬化。优先从剩余 broad except、日志打印边界或 `main()` DI 里挑一个最小闭环；不要重建已收掉的小 support 文件，不要切成人 BT 新功能，不改协议或 SQLite 真相边界。
```
