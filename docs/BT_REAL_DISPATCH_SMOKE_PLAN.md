# BT 真实 dispatch smoke (v1)

> 目的：把当前 promoted 主线从“BT 页面 URL proof”切到“BT 真实下载器投递 smoke”，先验证现有 BT 主链是否真的能把任务投递到 BT Transmission，而不是继续围着页面变体打转。

## 1. 要解决的真实问题

当前仓库已经完成了两类 BT 能力：

1. 只读页面预览、聊天缓存和 `bt批量确认` 复用；
2. BT / PT 角色绑定、`jobs` / approval / confirm / download_monitor 真相边界。

但还缺一条正式的真实证据：

- BT 输入真的会落到 `BT_DOWNLOADER=tr-bt`；
- `confirm` 后真的会投递到 `http://127.0.0.1:19092`；
- 失败时能直接定位到配置、下载器路由或 RPC 请求，而不是只停留在 mock proof。

所以这条主线先收“真实 dispatch”，不继续补页面 URL 变体，也不顺手放大成导入 / 刷新主线。

## 2. 当前最小闭环

当前只收这一条最小真实链路：

1. 用户发送一个直接 `magnet:?`；
2. shared runtime 进入现有 BT 分流；
3. 用户回复 `纯 BT 下载链`；
4. 用户选择一个已配置的 `raw_bt` 目标目录；
5. 系统进入现有下载 approval；
6. 用户发送 `confirm <task_ref>`；
7. 真实验证任务是否落到 `BT Transmission(http://127.0.0.1:19092)`。

为了稳定性，这条主线**固定使用 direct `magnet:?`**，不把 `nyaa` 页面可用性、外站波动或页面解析带回当前 promoted 主线。

## 3. Phase 顺序

1. Phase 1：补主线文档和 3 轮推进规则，明确 BT 页面 proof 家族已完成，不再继续拆更小页面形式。
2. Phase 2：写一次性 `tmp_tests/` 真实验证脚本，驱动 “magnet -> 纯 BT 下载链 -> raw_bt 目录 -> approval -> confirm”。
3. Phase 3：验证 `19092` 出现任务，并把真实成功或失败证据写回当前主线文档与 `STATUS.md`。

## 4. Done when

当前主线视为 **已收口**，满足以下任一条即可：

1. 真实 BT dispatch smoke 成功：`confirm` 后能在 `http://127.0.0.1:19092/transmission/rpc` 观察到新任务，且任务真相继续落在现有 approval / `jobs` / download_monitor 边界；
2. 真实 BT dispatch smoke 失败，但失败点已被收口到明确的 `downloader_name / request_url / 配置缺口`，并有显式中文日志与 `[处理建议]`；
3. 本轮代码变更 `< 20` 行且只是对同一个 dispatch / route helper 再补一条诊断分支，触发 `AGENTS.md §11` 停机规则。

## 5. 不做清单

- 不继续补 BT allowlist 页面 URL 变体 proof
- 不把这一步扩成 BT 批量确认真实 smoke
- 不把这一步扩成 BT 导入 / Emby refresh 主线
- 不接新站点、动态站点、CAPTCHA 或登录态站点
- 不改 approval / `jobs` / `job_event` / lease/version / SQLite 真相边界
