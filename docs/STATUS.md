# Current status (v548)

## Current mainline
- `质量硬化` 已完成，`adult BT minimum wedge` 已完成并已推送到 `main`。
- 本轮已落地：docs gate 恢复、`成人搜` 只读入口、javlibrary 只读详情 URL、成人历史透传到待下载回复、`verify-adult-bt-wedge`。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 保持完成态；`cleanup_*_support.py` 当前为 `0` 个。
- `app/config.py` 启动硬依赖解耦（方案 A）已完成并进一步延伸到 non-Telegram 宿主画像：`PROWLARR_*` 已收口成能力必填，legacy `TRANSMISSION_BASE_URL` 在已有可用 downloader instances 时可留空，`TELEGRAM_BOT_TOKEN` 现在改成 Telegram 宿主条件必填。
- `app/main.py` / `telegram_sidecar_runtime.py` 继续收口到 non-Telegram 第二阶段：Telegram 继续走 PTB host，Telegram 为空时会优先进入 WeCom-only 或 Feishu-only 的最小宿主路径。
- `telegram_sidecar_runtime.py` 宿主解耦已完成：sidecar/scheduler 生命周期已抽成通用 host 边界，Telegram 只保留 wrapper。
- `manage_bt_subscription.py` 首个超大业务文件收口切口已完成：候选选择 / 打分解析 helper 已下沉，`pure_bt` 与订阅路径已复用同一套 BT candidate metadata 解析实现。
- Feishu 可选依赖策略已完成：标准 `requirements.txt` 已显式包含 `lark-oapi==1.5.3`，operator docs 与运行时启用条件已对齐。
- 当前主线已额外完成：`lark_oapi` / `websockets` 已知 deprecation warnings 已在 Feishu 可选链路入口局部隔离，主线验证输出已恢复干净。
- 当前主线已落地 non-Telegram 入站宿主收口：`Feishu-only` / `WeCom-only` 在无 `TELEGRAM_BOT_TOKEN` 时都可以按各自凭据独立启动并收消息、回消息；无主动 `send_text` 能力的宿主会显式跳过 `btsub` 后台扫描。
- 当前主线继续补齐了 non-Telegram 后台通知的运行态联系人注册表：Feishu / WeCom / personal WeChat inbound 会在 `bot_data` 中记录外部会话地址，给后续后台回发解析留出可逆真相。
- 当前主线已补齐 `watchlist -> btsub` 桥接：`watchlist sync` / `想看 同步` 会把想看清单原子同步进 BT 订阅，保持手动想看语义和 `confirm` 边界不变。
- 下一条唯一主线切到扩展 BT subscription 边界；优先锁定 raw BT subscription 的最小 contract，不回切 non-Telegram 通知或 richer reply 主线。

## Current health
- `make verify-adult-bt-wedge` 通过（总计 `423 passed`）。
- `make quality` 通过（`28 passed`）。
- `make verify-mainline` 通过。
- `make lint` 通过。
- focused tests：`tests/test_manage_watchlist.py` / `tests/test_private_chat_watchlist_runtime.py` / `tests/test_main.py` / `tests/test_manage_bt_subscription.py` / `tests/test_persistence_sqlite.py` 当前新增的 watchlist bridge、main wiring、BT subscription repo 原子写入回归已通过。
- Telegram 人工 smoke：应用已启动，当前会话待验证。
- 当前 active docs root：`15`；docs gate 绿灯。

## Latest verification
- `.venv/bin/python -m pytest -q tests/test_manage_watchlist.py tests/test_private_chat_watchlist_runtime.py tests/test_execution_runtime.py tests/test_main.py -k 'watchlist or qb_only_runtime_without_prowlarr_or_legacy_transmission'` 通过。
- `.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k 'add_list_remove_clear_and_restart or run_scheduler_tick or run_once or add_returns_failure_text_when_repo_returns_none'` 通过。
- `.venv/bin/python -m pytest -q tests/test_persistence_sqlite.py -k 'bt_subscription_repo'` 通过。
- `make quality` 通过。
- `make verify-mainline` 通过。
- `make lint` 通过。
- `make verify-adult-bt-wedge` 通过（195 + 174 + 54 三组均通过）。
- active docs root 预算验证：排除 `PROGRESS.md` / `BLOCKERS.md` 后为 `15`。
- 当前主线额外信号：watchlist bridge 现在不会在同步失败时留下部分成功；重复 `watchlist sync` 会稳定计入“已存在”，不重写 `btsub` 语义。

## Current biggest risk
- 当前最大风险已经切到 `BT subscription` 扩边本身：下一轮若同时混入 raw BT 订阅、auto-confirm、多渠道通知或 richer reply，会重新把主线做胖。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md 执行单轮主线施工。

当前唯一主线切到扩展 BT subscription 边界。`watchlist sync` / `想看 同步` 已完成；下一轮优先锁定 raw BT subscription 的最小 contract，继续保持 `confirm` 边界，不改 SQLite schema，也不要顺手做 auto-confirm、通知渠道扩边或 richer reply。
```
