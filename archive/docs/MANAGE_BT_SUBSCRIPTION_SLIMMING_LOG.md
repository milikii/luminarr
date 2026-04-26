# Manage BT subscription slimming log (v2)

> 目的：承接当前“`manage_bt_subscription.py` 订阅编排层瘦身 / 模块化”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Completed line

- 已完成主线：`manage_bt_subscription.py` 订阅编排层瘦身 / 模块化（已在 2026-04-19 满足 `Done when` 第 1 条：`app/services/bt_subscription_command.py` 已承接命令解析 / 标题解析 / 清单回复边界，且 focused tests `17 passed, 20 deselected`）
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

本轮收口：
- `app/services/bt_subscription_command.py` 现在承接 `parse_bt_subscription_query()`、媒体类型前缀解析、标题年份抽取和清单增删回复文本；`manage_bt_subscription.py` 只保留 repo 调用、扫描命中、`last_seen` 更新和现有 fail-closed 中文日志边界。
- 这一组收口只动订阅清单入口；扫描候选筛选、`last_seen` 回写、下载待确认创建和 scheduler tick 未改。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "parse_bt_subscription_query or add or list or remove or clear"`

### 2.2 扫描候选筛选 / `last_seen` 更新 / scheduler tick

剩余风险：
- `manage_bt_subscription.py` 还把 `_scan_chat_once()`、候选排序、`_update_last_seen()`、`run_once()` / `run_scheduler_tick()` 和下载待确认 follow-up 混在同一文件，但这一组已经不再阻塞主线切换。
- 这一组后续只作为上一条已完成主线的剩余结构证据保留，继续守住“命中新资源仍先走现有 downloader approval -> confirm 边界；`last_seen` 写入失败只打显式中文日志 + `[处理建议]`，不把坏真相混成已成功追踪”的边界。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "run_once or scheduler_tick or last_seen"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "parse_bt_subscription_query or add or list or remove or clear"`
- `.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "run_once or scheduler_tick or last_seen"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.2 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 当前唯一主线已经切到 `docs/CLEANUP_SLIMMING_LOG.md`；本文件只继续保留完成态路径和 focused tests 入口。
