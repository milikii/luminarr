# Current status (v547)

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
- 下一条唯一主线切到 non-Telegram 后台主动通知所需的可逆会话真相；不回切 `services` 结构降本主线。

## Current health
- `make verify-adult-bt-wedge` 通过（总计 `423 passed`）。
- `make quality` 通过（`28 passed`）。
- `make verify-mainline` 通过。
- focused tests：`tests/test_config.py` / `tests/test_main.py` / `tests/test_channel_contact_runtime.py` 当前新增的 Feishu-only / WeCom-only 启动契约、scheduler guard 与联系人注册表用例已通过。
- Telegram 人工 smoke：应用已启动，当前会话待验证。
- 当前 active docs root：`15`；docs gate 绿灯。

## Latest verification
- `make verify-adult-bt-wedge` 通过（195 + 174 + 54 三组均通过）。
- `.venv/bin/python -m pytest -q tests/test_channel_contact_runtime.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_personal_wechat_text.py tests/test_config.py tests/test_main.py -k 'contact or records or routes_into_shared_runtime or non_telegram_host or telegram_token or allows_missing_telegram_token or rejects_missing_telegram_token_without_feishu_host or rejects_partial_feishu_credentials_without_telegram_token or bt_subscription_scheduler_skips_without_send_text_callback'` 通过。
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py` 通过。
- `make quality` 通过。
- `make verify-mainline` 通过。
- `make lint` 通过。
- active docs root 预算验证：排除 `PROGRESS.md` / `BLOCKERS.md` 后为 `15`。
- 当前主线额外信号：`Feishu-only` / `WeCom-only` 启动路径都已不再依赖 Telegram polling；non-Telegram 宿主不会再把缺失的后台主动通知伪装成可用。

## Current biggest risk
- 当前风险不再是“画像未锁定”，而是后续若同时去碰后台主动通知可逆会话真相和 personal WeChat 登录重做，会重新把 non-Telegram 主线做胖。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md 执行单轮主线施工。

当前唯一主线切到 non-Telegram 后台主动通知所需的可逆会话真相。`Feishu-only` / `WeCom-only` 独立宿主都已完成；下一轮不要顺手收口 `app/bot/private_chat_runtime.py` 对 `app/bot/telegram_bot.py` 的残余 helper 依赖，不改 SQLite schema 或 BT/PT 主链语义。
```
