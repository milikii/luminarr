# Current status (v544)

## Current mainline
- `质量硬化` 已完成，`adult BT minimum wedge` 已完成并已推送到 `main`。
- 本轮已落地：docs gate 恢复、`成人搜` 只读入口、javlibrary 只读详情 URL、成人历史透传到待下载回复、`verify-adult-bt-wedge`。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 保持完成态；`cleanup_*_support.py` 当前为 `0` 个。
- `app/config.py` 启动硬依赖解耦（方案 A）已完成：`PROWLARR_*` 已收口成能力必填，legacy `TRANSMISSION_BASE_URL` 在已有可用 downloader instances 时可留空，`TELEGRAM_BOT_TOKEN` 继续保持当前宿主必填。
- `telegram_sidecar_runtime.py` 宿主解耦已完成：sidecar/scheduler 生命周期已抽成通用 host 边界，Telegram 只保留 wrapper。
- `manage_bt_subscription.py` 首个超大业务文件收口切口已完成：候选选择 / 打分解析 helper 已下沉，`pure_bt` 与订阅路径已复用同一套 BT candidate metadata 解析实现。
- Feishu 可选依赖策略已完成：标准 `requirements.txt` 已显式包含 `lark-oapi==1.5.3`，operator docs 与运行时启用条件已对齐。
- 当前主线已额外完成：`lark_oapi` / `websockets` 已知 deprecation warnings 已在 Feishu 可选链路入口局部隔离，主线验证输出已恢复干净。
- 下一条唯一主线切到把 non-Telegram 运行模式做成一等公民；不回切 `services` 结构降本主线。

## Current health
- `make verify-adult-bt-wedge` 通过（总计 `422 passed`）。
- `make quality` 通过（`28 passed`）。
- `make verify-mainline` 通过。
- Telegram 人工 smoke：应用已启动，当前会话待验证。
- 当前 active docs root：`15`；docs gate 绿灯。

## Latest verification
- `make verify-adult-bt-wedge` 通过（195 + 173 + 54 三组均通过）。
- `make quality` 通过（`28 passed`）。
- `make verify-mainline` 通过。
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py` 通过。
- active docs root 预算验证：排除 `PROGRESS.md` / `BLOCKERS.md` 后为 `15`。
- 当前主线额外信号：已不再看到已知 `lark_oapi` / `websockets` deprecation warnings，暂无新失败。

## Current biggest risk
- 当前风险不是前五条主线回归，而是“non-Telegram 运行模式做成一等公民”会同时触碰入口、部署、通知回路和宿主真相边界；如果不先锁定最小交付画像，很容易从宿主解耦滑成整条多渠道产品面重做。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md 执行单轮主线施工。

当前唯一主线切到把 non-Telegram 运行模式做成一等公民。先盘点当前还依赖 Telegram 宿主的入口、通知与部署真相，锁定“最小可单独运行画像”后再推进；不要回切宿主/配置/超大文件/依赖告警主线，不改 SQLite schema 或 BT/PT 主链语义。
```
