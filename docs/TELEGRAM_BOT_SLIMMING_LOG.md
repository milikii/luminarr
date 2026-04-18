# Telegram bot slimming log (v1)

> 目的：承接当前“`telegram_bot.py` 渠道层瘦身 / 模块化”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 当前唯一主线：`telegram_bot.py` 渠道层瘦身 / 模块化
- 上一条主线“独立后台下载完成轮询剩余少量回归与验证收口”已在 2026-04-18 满足退出条件 1；详细台账继续只看 `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 更早主线“Feishu 私聊事件解析器去重”已完成；详细台账继续只看 `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线“Feishu 长连接私有 API 风险收口”已完成；详细台账继续只看 `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线“持久化吞错收口”已完成；详细台账继续只看 `docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## 2. Risk groups

### 2.1 收包回包 / shared runtime wrapper

当前风险：
- `telegram_bot.py` 仍同时维护 Telegram 文本 / callback 收包、shared runtime 包装和部分回复入口；这一步只允许把这组“协议差异 + 调 shared runtime”的壳继续收成更小的仓库自管 helper，不改 Telegram update 去重和现有回复协议。
- 这一组只允许动 Telegram 渠道壳；不顺手改 shared runtime、approval、`jobs` 和 SQLite 真相。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "handle_callback_query or build_application"`

### 2.2 后台生命周期 / BT pending helper

当前风险：
- `telegram_bot.py` 还把下载完成轮询、订阅 scheduler、Feishu / WeCom / personal WeChat 启停，以及 BT pending helper 的 set / clear / pop 混在同一文件里；这一步只允许按一组连贯 helper 拆开，不能顺手改状态真相或副作用边界。
- 这一组继续守住下载完成轮询、BT pending 和跨渠道后台服务的显式中文日志 + `[处理建议]`，不把现有 fail-closed 边界改松。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_private_chat_runtime.py -k "post_download_auto_import_scheduler or bt_processing_path or bt_classification or bt_tmdb_association or raw_bt_destination"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "handle_callback_query or build_application"`
- `.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_private_chat_runtime.py -k "post_download_auto_import_scheduler or bt_processing_path or bt_classification or bt_tmdb_association or raw_bt_destination"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.2 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 只有当当前主线完成并切到下一项时，才在 `docs/NEXT_STEP.md` 和 `README.md` 切换“当前唯一主线”。
