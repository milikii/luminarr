# Current status (v544)

## Current mainline
- `质量硬化` 已完成，`adult BT minimum wedge` 已完成并已推送到 `main`。
- 本轮已落地：docs gate 恢复、`成人搜` 只读入口、javlibrary 只读详情 URL、成人历史透传到待下载回复、`verify-adult-bt-wedge`。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 保持完成态；`cleanup_*_support.py` 当前为 `0` 个。
- `app/config.py` 启动硬依赖解耦（方案 A）已完成：`PROWLARR_*` 已收口成能力必填，legacy `TRANSMISSION_BASE_URL` 在已有可用 downloader instances 时可留空，`TELEGRAM_BOT_TOKEN` 继续保持当前宿主必填。
- `telegram_sidecar_runtime.py` 宿主解耦已完成：sidecar/scheduler 生命周期已抽成通用 host 边界，Telegram 只保留 wrapper。
- `manage_bt_subscription.py` 首个超大业务文件收口切口已完成：候选选择 / 打分解析 helper 已下沉，`pure_bt` 与订阅路径已复用同一套 BT candidate metadata 解析实现。
- Feishu 可选依赖策略已完成：标准 `requirements.txt` 已显式包含 `lark-oapi==1.5.3`，operator docs 与运行时启用条件已对齐。
- 下一条唯一主线切到清理当前依赖告警；不回切 `services` 结构降本主线。

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
- 当前风险不是前四条主线回归，而是 `lark_oapi` / `websockets` deprecation warnings 仍持续出现在主线验证输出里；如果继续放着不收口，会降低后续 smoke 和真实失败信号的可读性。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md 执行单轮主线施工。

当前唯一主线切到清理当前依赖告警。先盘点 `lark_oapi` / `websockets` warnings 的来源，优先找“升级版本 / 局部隔离 warnings / 最小兼容修补”三种路径里差异最小的一条；不要回切宿主/配置/超大文件主线，不改 SQLite schema 或 BT/PT 主链语义。
```
