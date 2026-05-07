# BLOCKERS.md

## 2026-05-07 — Telegram 真实 smoke 仍被宿主网络阻断

- `05-02-telegram-real-smoke-restore` 已复核到新的环境真相：`api.telegram.org` 的 DNS 已恢复，但宿主网络直连仍 `curl` 超时（`http=000`）。
- 当前 `.env` 虽保留 `OUTBOUND_PROXY_URL` 配置键，但该值在本机当前 shell 路径下为空，无法作为 Telegram 出口兜底。
- `timeout 25 .venv/bin/python -m app.main` 已证明本地进程可以启动，说明 blocker 不再是 “`app.main` 起不来”，而是 “没有可用 Telegram 出口，无法补新的真实入站 smoke”。
- 解除方式：先恢复直连 `api.telegram.org` 或补回可用代理，再保持本地 `app.main` 持续运行并做一次真实 Telegram 入站复验。

## 2026-05-07 — 当前无环境 blocker，等待新的真实 Telegram 入站证据

- 上一轮“token 为空”的判断已确认是 shell 引号探针误判，不是 `.env` 真相。
- 修正后的探针已确认：`.env` 中 `TELEGRAM_BOT_TOKEN` 非空且格式正确，默认代理非空；替代代理 `http://192.168.2.220:7890` 也可用。
- 通过该代理调用 Telegram Bot API `getMe` 已返回 `200 / ok=true`，说明当前环境前置条件已恢复。
- `logs/trace.log` 已新增同会话真实 Telegram 入站证据（`ping` / `start` 及对应回包），说明“入站恢复”已完成。
- 当前还没有新的环境 blocker；剩余动作是补一条新的 `PT 资源选择 -> 下载 -> 导入/后处理` 同会话 smoke 证据链。
- `2026-05-07 15:35` 这轮 `功夫熊猫` 已补到 `dispatch -> 下载状态 ✓`，但因为复用了既有任务 hash `46b907...`，没有继续刷新新的 `import.* / metadata.* / subtitle.* / refresh.*` 事件。
- `2026-05-07 15:56` 这轮 `超人` 已补到 fresh hash `52bde7...` 的 `dispatch -> 已添加下载 -> 下载状态 ⏳`；当前不是 blocker，而是等待下载完成后继续观察新的导入与后处理事件。
- `2026-05-07 16:28` 已实测确认：重启 `app.main` 后，`52bde7...` 的 Telegram 进度卡片仍会继续同步，不再停在重启前的旧进度。
- `2026-05-07 19:48` `52bde7...` 已完成 fresh-hash 导入与后处理闭环；当前没有 Telegram smoke 环境 blocker。

## 2026-05-07 — 流程文档任务收尾验证被现有质量红灯阻断

- 本轮仅新增 `docs/flows/` 下的流程文档，没有改业务代码；`./.venv/bin/python -m pytest tests/test_cleanup_docs_consistency.py` 已通过，说明 docs gate 未被新文档打坏。
- `make quality` 与 `make lint` 当前都失败在同一个既有问题：`app/bot/telegram_update_runtime.py:240` 存在未使用局部变量 `task_identity`。
- `make verify-mainline` 当前失败在两条既有断言：`tests/test_telegram_bot.py::test_handle_message_digit_routes_to_add_service` 与 `tests/test_telegram_bot.py::test_handle_callback_query_digit_routes_to_add_service` 仍期待 `📍 当前状态：等待下载器首次同步`，而当前真实回复文本是 `状态：等待下载器同步`。
- 解除方式：单独修复上述 lint / 测试漂移后，再重跑 `make quality`、`make verify-mainline`、`make lint`；本轮流程文档可继续使用，但仓库当前不满足“全仓全绿”。

## 2026-05-08 — 流程文档任务收尾验证红灯已解除

- 已删除 `app/bot/telegram_update_runtime.py:240` 的未使用局部变量 `task_identity`，`make lint` 与 `make quality` 恢复通过。
- 已将 `tests/test_telegram_bot.py` 中 2 条 Telegram add-success 断言对齐到当前真实文案 `状态：等待下载器同步`，`make verify-mainline` 恢复通过。
- 当前这组收尾验证 blocker 已解除；后续若再出现红灯，应按新的失败点单独记录。
