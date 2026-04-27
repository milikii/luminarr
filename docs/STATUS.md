# Current status (v511)

## Current mainline
- **质量硬化** 继续保持完成态；当前唯一主线仍是 **质量债硬化 / 异常边界、日志边界和 DI 收口**。
- 本轮按文档继续完成 10 个最小闭环：新增共享 `bt_pending_runtime`，并把 `bt_processing_path`、`bt_classification`、`bt_tmdb_association`、`raw_bt_destination` 的 BT pending repo 解析、payload 编解码和持久化日志统一到该边界；同时收口 pure BT / BT TMDB / BT read-only / BT source 日志格式和刷新边界。
- 成人归档上层不再用泛 `Exception` 判断归档/清理失败；文件搬运、下载器删除和本地源清理失败进入明确操作失败文本，持久化失败仍保持状态不可用边界。
- 默认分支协议、SQLite schema、下载/导入/审批语义未变化；本轮主要是 BT pending runtime 结构减法和日志边界收口。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 通过；本轮 focused tests 已覆盖 BT direct / processing path / classification / TMDB association / raw destination / read-only / BT source 日志路径。
- `make quality` 通过，`make verify-mainline` 通过。
- 下一轮继续质量债时，优先从剩余 broad `except Exception` 中区分“外部服务隔离”与“repo/SQLite 持久化边界”，或继续收口日志打印边界 / `main()` DI；不要切成人 BT 新功能。

## Latest verification
- BT pending / direct / classification / TMDB / raw destination focused：`77 passed, 194 deselected`
- BT read-only / history / JavLibrary / batch preview focused：`93 passed, 102 deselected`
- BT read-only runtime / BT source focused：`140 passed, 319 deselected`
- `make quality`：通过（`27 passed, 0 skipped`）
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
