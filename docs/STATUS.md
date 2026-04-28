# Current status (v544)

## Current mainline
- `质量硬化` 已完成，`adult BT minimum wedge` 已完成并已推送到 `main`。
- 本轮已落地：docs gate 恢复、`成人搜` 只读入口、javlibrary 只读详情 URL、成人历史透传到待下载回复、`verify-adult-bt-wedge`。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 保持完成态；`cleanup_*_support.py` 当前为 `0` 个。
- `app/config.py` 启动硬依赖解耦（方案 A）已完成：`PROWLARR_*` 已收口成能力必填，legacy `TRANSMISSION_BASE_URL` 在已有可用 downloader instances 时可留空，`TELEGRAM_BOT_TOKEN` 继续保持当前宿主必填。
- 下一条唯一主线切到 `app/bot/telegram_sidecar_runtime.py` 宿主解耦；不回切 `services` 结构降本主线。

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
- 当前主线额外信号：仍保留 `lark_oapi` / `websockets` deprecation warnings，暂无新失败。

## Current biggest risk
- 当前风险不是 config 主线回归，而是下一轮 `telegram_sidecar_runtime.py` 宿主解耦会触碰运行时宿主边界：Feishu、WeCom、personal WeChat、自动导入轮询和 `btsub` scheduler 目前都仍挂在 Telegram `Application` 生命周期下，拆分时需要避免把现有私聊入口和后台任务一起带坏。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md 执行单轮主线施工。

当前唯一主线切到 app/config.py 启动硬依赖解耦。按已定稿方案 A 推进：先把 PROWLARR_* 与 legacy TRANSMISSION_BASE_URL 从全局硬必填收口成按能力判定；TELEGRAM_BOT_TOKEN 继续保持当前宿主必填，同时把 capability contract 落到启动装配、runtime guard、focused tests 和文档里；不要回切 services 结构降本，不改 SQLite schema 或 BT/PT 主链语义。
当前唯一主线切到 app/bot/telegram_sidecar_runtime.py 宿主解耦。先盘点 Telegram `Application` 生命周期下当前承载的 Feishu、WeCom、personal WeChat、自动导入轮询与 `btsub` scheduler，拆出非 Telegram 也能承载的宿主边界；不要回切 services 结构降本，不改 SQLite schema 或 BT/PT 主链语义。
```
