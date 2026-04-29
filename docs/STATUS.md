# Current status (v551)

## Current mainline
- `质量硬化` 已完成，`adult BT minimum wedge` 已完成并已推送到 `main`。
- 本轮已落地：docs gate 恢复、`成人搜` 只读入口、javlibrary 只读详情 URL、成人历史透传到待下载回复、`verify-adult-bt-wedge`。
- `shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口` 保持完成态；`cleanup_*_support.py` 当前为 `0` 个。
- `app/config.py` 启动硬依赖解耦（方案 A）已完成并进一步延伸到 non-Telegram 宿主画像：`PROWLARR_*` 已收口成能力必填，legacy `TRANSMISSION_BASE_URL` 在已有可用 downloader instances 时可留空，`TELEGRAM_BOT_TOKEN` 现在改成 Telegram 宿主条件必填。
- `app/main.py` / `telegram_sidecar_runtime.py` 继续收口到 non-Telegram 第二阶段：Telegram 继续走 PTB host，Telegram 为空时会优先进入 WeCom-only 或 Feishu-only 的最小宿主路径。
- `telegram_sidecar_runtime.py` 宿主解耦已完成：sidecar/scheduler 生命周期已抽成通用 host 边界，Telegram 只保留 wrapper。
- `manage_bt_subscription.py` 首个超大业务文件收口切口已完成：候选选择 / 打分解析 helper 已下沉，`pure_bt` 与订阅路径已复用同一套 BT candidate metadata 解析实现。
- 运行时外部依赖真相页已收口到 `docs/GETTING_STARTED.md`；`README.md`、`docs/OPERATOR_RUNBOOK.md`、本页现在只保留引用或短提示。
- 当前主线已额外完成：`lark_oapi` / `websockets` 已知 deprecation warnings 已在 Feishu 可选链路入口局部隔离，主线验证输出已恢复干净。
- 当前主线已落地 non-Telegram 入站宿主收口：`Feishu-only` / `WeCom-only` 在无 `TELEGRAM_BOT_TOKEN` 时都可以按各自凭据独立启动并收消息、回消息；无主动 `send_text` 能力的宿主会显式跳过 `btsub` 后台扫描。
- 当前主线继续补齐了 non-Telegram 后台通知的运行态联系人注册表：Feishu / WeCom / personal WeChat inbound 会在 `bot_data` 中记录外部会话地址，给后续后台回发解析留出可逆真相。
- 当前主线已收口 `watchlist sync`：`想看` 清单继续只服务 PT 主线，`watchlist sync` / `想看 同步` 现在会显式 fail-closed，不再桥接到 `btsub`。
- 当前真相重新锁定到 2026-04-26 / 2026-04-29 已定边界：BT 支线只承接成人资源，不从 BT 线索取任何影视资源，包括动漫。
- direct `BT` / `magnet:?` 投递入口继续保留 `观影 PT 链 / BT 成人链` 问询，不允许绕过问询把 BT 投递默认解释成成人 BT。
- 当前主线已把 `btsub add` 收口成成人 BT 精确番号追踪；旧的非成人订阅条目会显式告警并跳过扫描。
- 当前主线已补齐成人 BT 连续追踪最小 contract：同标题但不同 URL 的镜像命中不再重复创建下载待确认，`btsub list` 现在会明确展示“上次命中资源”。
- Telegram 成人 BT 真机 smoke 已完成：`2026-04-28` 在真实 Telegram 私聊里完成了 `成人搜 SSIS-483`、direct magnet、`BT 成人链`、`confirm bt-372f049d` 和 `status 3849...` 的最小闭环。
- `search_media.py` 的候选/澄清状态持久化 helper 已抽到 `app/services/search_media_state.py`，当前 focused tests 证明这次切口未改变重启恢复与 fail-closed 语义。
- 后续若还要继续扩 `BT subscription`，也只允许面向成人 BT 连续追踪，不回切 raw BT / 影视资源订阅主线。

## Current health
- `make verify-adult-bt-wedge` 通过（总计 `423 passed`）。
- `make quality` 通过（`28 passed`）。
- `make verify-mainline` 通过。
- `make lint` 通过。
- focused tests：`tests/test_bt_subscription_candidate_helpers.py` / `tests/test_manage_bt_subscription.py` 当前新增的 same-title 去重与“上次命中资源”文案回归已通过。
- Telegram 成人 BT 真机 smoke：已完成（`2026-04-28`）。
- `search_media` 状态抽取 focused tests：`tests/test_search_media.py` 通过（`187 passed`）。
- 当前 active docs root：`15`；docs gate 绿灯。

## Latest verification
- `.venv/bin/python -m pytest -q tests/test_bt_subscription_candidate_helpers.py tests/test_manage_bt_subscription.py` 通过（`50 passed`）。
- `make quality` 通过。
- `make verify-mainline` 通过。
- `make lint` 通过。
- `make verify-adult-bt-wedge` 通过（195 + 174 + 54 三组均通过）。
- `.venv/bin/python -m pytest -q tests/test_search_media.py` 通过（`187 passed`）。
- Telegram 成人 BT 真机 evidence：`logs/trace.log` 已记录 `成人搜 SSIS-483`、direct magnet、`BT 成人链`、`confirm bt-372f049d`、`status 3849...`；`job_event` 里可见同任务的 `approval_pending -> approval_confirmed -> downloader.succeeded`。
- active docs root 预算验证：排除 `PROGRESS.md` / `BLOCKERS.md` 后为 `15`。
- 当前主线额外信号：`watchlist sync` 现在只回 PT 主线边界提示；`btsub add` 不再接受影视订阅输入，旧的非成人订阅条目也不会再被静默扫描；同标题镜像资源不会重复报成“新资源”。

## Current biggest risk
- 当前最大风险已经切到“完成态失守”：如果没有新证据就重新打开旧主线，最容易把当前已经收口的成人 BT 边界、依赖真相页或结构切口再次带偏。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md 执行单轮主线施工。

当前 `docs/TASKS.md` 已全部完成，先做冷启动一致性检查；若没有新的失败证据或新需求，保持冻结，不要自行重开成人 BT 扩边、non-Telegram 通知或更大范围结构降本主线。
```
