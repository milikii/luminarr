# Current status (v518)

## Current mainline
- **质量硬化** 继续保持完成态；当前唯一主线仍是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮继续完成外部客户端异常边界收口：`metadata_scraper` 的 TMDB/Fanart/图片下载、`search_media` 的 BT 只读搜索/页面预览、`bt_sources` provider 搜索/页面搜索、`manage_bt_subscription` 订阅扫描搜索失败只捕获明确 `httpx.HTTPError` / `ValueError`。
- 本轮补了 BT 订阅扫描搜索失败的 focused regression，并把相关测试里的网络失败模拟从泛 `RuntimeError` 调整为真实 `httpx.ConnectError`。
- 本轮只改异常捕获类型和测试输入，不改协议、SQLite schema、下载/导入/刷新/订阅扫描语义，也没有引入新增用户可感知功能。
- 本轮 focused tests 已通过；`make quality`、`make verify-mainline` 均重新通过。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 通过；本轮 focused tests 覆盖 metadata 刮削、BT 来源、搜索展示和 BT 订阅扫描路径。
- 本轮未触发真实 downloader / refresh 协议行为变化；改动为外部客户端异常边界收窄，并由 focused tests 与 mainline gate 覆盖。
- `make quality` 通过（`27 passed, 0 skipped`），`make verify-mainline` 通过。
- 下一轮继续质量债时，优先从剩余 broad `except Exception` 中区分“外部服务隔离”与“repo/SQLite 持久化边界”，或继续收口剩余日志打印边界 / `main()` DI；不要切成人 BT 新功能。

## Latest verification
- `tests/test_metadata_scraper.py tests/test_search_media.py tests/test_bt_sources.py tests/test_manage_bt_subscription.py` 通过（`253 passed`）。
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
