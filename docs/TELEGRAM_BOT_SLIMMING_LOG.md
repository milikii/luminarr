# Telegram bot slimming log (v1)

> 目的：承接当前“`telegram_bot.py` 渠道层瘦身 / 模块化”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Completed line

- 已完成主线：`telegram_bot.py` 渠道层瘦身 / 模块化（已在 2026-04-19 满足 `Done when` 第 1 条：`app/bot/telegram_runtime_adapter.py` 已承接 `handle_message()` / `handle_callback_query()` / `build_application()` 协议壳，且 focused tests `13 passed, 140 deselected`）
- 上一条已完成主线“独立后台下载完成轮询剩余少量回归与验证收口”已在 2026-04-18 满足退出条件 1；详细台账继续只看 `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 更早主线“Feishu 私聊事件解析器去重”已完成；详细台账继续只看 `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线“Feishu 长连接私有 API 风险收口”已完成；详细台账继续只看 `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线“持久化吞错收口”已完成；详细台账继续只看 `docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## 2. Risk groups

### 2.1 收包回包 / shared runtime wrapper

本轮收口：
- `handle_message()`、`handle_callback_query()` 和 `build_application()` 现在统一委托给 `app/bot/telegram_runtime_adapter.py`；`telegram_bot.py` 保留原导出函数名和现有回复协议，不回退 Telegram update / callback 去重边界。
- 这组收口只动 Telegram 渠道壳；shared runtime、approval、`jobs` 和 SQLite 真相未改。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "handle_callback_query or build_application"`

### 2.2 后台生命周期 / BT pending helper

剩余风险：
- `telegram_bot.py` 里仍有后台生命周期、BT pending helper 和跨渠道启停逻辑混在同一文件，但它们已不再阻塞当前主线切换。
- 这一组后续只作为更早完成态证据保留，继续守住下载完成轮询、BT pending 和跨渠道后台服务的显式中文日志 + `[处理建议]`。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_private_chat_runtime.py -k "post_download_auto_import_scheduler or bt_processing_path or bt_classification or bt_tmdb_association or raw_bt_destination"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "handle_callback_query or build_application"`
- `.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_private_chat_runtime.py -k "post_download_auto_import_scheduler or bt_processing_path or bt_classification or bt_tmdb_association or raw_bt_destination"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.2 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 当前唯一主线已经切到 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`；本文件只继续保留完成态路径和 focused tests 入口。
