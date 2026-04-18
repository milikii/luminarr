# Manage BT subscription slimming log (v1)

> 目的：承接当前“`manage_bt_subscription.py` 订阅编排层瘦身 / 模块化”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 当前唯一主线：`manage_bt_subscription.py` 订阅编排层瘦身 / 模块化
- 上一条已完成主线“`search_media.py` 搜索编排层瘦身 / 模块化”已在 2026-04-19 满足 `Done when` 第 1 条：`app/services/search_request_context.py` 已承接 query 解析 / TMDB 查询 / 搜索请求编排边界，且 focused tests `12 passed, 27 deselected`
- 更早已完成主线“`add_to_downloader.py` 下载编排层瘦身 / 模块化”已在 2026-04-19 满足退出条件 1；详细台账继续只看 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`
- 更早已完成主线“`import_to_library.py` 导入编排层瘦身 / 模块化”已在 2026-04-19 满足退出条件 1；详细台账继续只看 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`
- 更早已完成主线“`telegram_bot.py` 渠道层瘦身 / 模块化”已在 2026-04-19 满足退出条件 1；详细台账继续只看 `docs/TELEGRAM_BOT_SLIMMING_LOG.md`
- 更早主线“独立后台下载完成轮询剩余少量回归与验证收口”已完成；详细台账继续只看 `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 更早主线“Feishu 私聊事件解析器去重”已完成；详细台账继续只看 `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线“Feishu 长连接私有 API 风险收口”已完成；详细台账继续只看 `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线“持久化吞错收口”已完成；详细台账继续只看 `docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## 2. Risk groups

### 2.1 清单增删 / 标题解析 / 回复文本

当前风险：
- `manage_bt_subscription.py` 还把 `parse_bt_subscription_query()`、`handle()` 分发、`_add_text()` / `_list_text()` / `_remove_text()` / `_clear_text()` 和 repo 写入后的中文回复揉在同一文件；这一步只允许把“命令解析 + 清单增删回复壳”继续收成 helper，不改 `bt_subscription_item` 真相和现有 fail-closed 中文提示协议。
- 这一组只允许动订阅清单入口，不顺手改扫描候选筛选、`last_seen` 回写、下载待确认创建或 scheduler tick。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "parse_bt_subscription_query or add or list or remove or clear"`

### 2.2 扫描候选筛选 / `last_seen` 更新 / scheduler tick

当前风险：
- `manage_bt_subscription.py` 还把 `_scan_chat_once()`、候选排序、`_update_last_seen()`、`run_once()` / `run_scheduler_tick()` 和下载待确认 follow-up 混在同一文件；这一步只允许按一组连贯 helper 拆开，不能顺手改 downloader approval 边界、自动扫描停路规则或 SQLite 真相。
- 这一组继续守住“命中新资源仍先走现有 downloader approval -> confirm 边界；`last_seen` 写入失败只打显式中文日志 + `[处理建议]`，不把坏真相混成已成功追踪”的边界。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "run_once or scheduler_tick or last_seen"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "parse_bt_subscription_query or add or list or remove or clear"`
- `.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "run_once or scheduler_tick or last_seen"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.2 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 当前唯一主线已经切到 `docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`；`docs/SEARCH_MEDIA_SLIMMING_LOG.md` 只继续保留完成态路径和 focused tests 入口。
