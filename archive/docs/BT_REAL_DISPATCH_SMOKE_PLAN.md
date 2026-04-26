# BT 真实 dispatch smoke (v2)

> 目的：保留这条刚完成的主线蓝图。2026-04-20 已用 direct `magnet:? -> 纯 BT 下载链 -> raw_bt 目录选择 -> confirm` 在 `BT Transmission(http://127.0.0.1:19092)` 观察到真实任务，当前不再把它当作 promoted 主线继续推进。

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

## 4. 完成证据

- 2026-04-20 真实验证脚本 `tmp_tests/verify_bt_real_dispatch_smoke.py` 已成功跑通：
  - direct `magnet:?` 先进入 BT 处理链问询；
  - 选择 `纯 BT 下载链` 后进入 `raw_bt` 目录选择；
  - 选择目录键 `smoke`，目标路径为 `/downloads/complete/raw_bt_smoke`；
  - 生成待确认 `task_ref=bt-ffe44b7b`；
  - `confirm bt-ffe44b7b` 后返回 `任务 ID: 1`、`任务 Hash: 03c970d927a04ef5a784fa1f9472c19e298fa754`；
  - 在 `http://127.0.0.1:19092/transmission/rpc` 观察到该任务，且 `downloadDir=/downloads/complete/raw_bt_smoke`。
- approval / jobs 真相均已落稳：
  - pending approval 能正常创建；
  - confirm 后 approval 进入 `approved` 且 `executed_version > 0`；
  - jobs 进入 `completed`，并保留 `downloader_name=tr-bt` 与 `download_dir=/downloads/complete/raw_bt_smoke`。
- 这条链当前是 `raw_bt + auto_import_enabled=False`，因此 **不会登记 `download_monitor`**；这不是回归，而是现有边界本身。

按 2026-04-20 当时的退出条件，这条主线已满足“真实 BT dispatch smoke 成功”。

## 5. 不做清单

- 不继续补 BT allowlist 页面 URL 变体 proof
- 不把这一步扩成 BT 批量确认真实 smoke
- 不把这一步扩成 BT 导入 / Emby refresh 主线
- 不接新站点、动态站点、CAPTCHA 或登录态站点
- 不改 approval / `jobs` / `job_event` / lease/version / SQLite 真相边界
