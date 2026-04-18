# Search media slimming log (v1)

> 目的：承接当前“`search_media.py` 搜索编排层瘦身 / 模块化”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 当前唯一主线：`search_media.py` 搜索编排层瘦身 / 模块化
- 上一条已完成主线“`add_to_downloader.py` 下载编排层瘦身 / 模块化”已在 2026-04-19 满足 `Done when` 第 1 条：`app/services/add_pending_context.py` 已承接候选选择 / 来源解析 / 待确认上下文边界，且 focused tests `21 passed, 88 deselected`
- 更早已完成主线“`import_to_library.py` 导入编排层瘦身 / 模块化”已在 2026-04-19 满足退出条件 1；详细台账继续只看 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`
- 更早已完成主线“`telegram_bot.py` 渠道层瘦身 / 模块化”已在 2026-04-19 满足退出条件 1；详细台账继续只看 `docs/TELEGRAM_BOT_SLIMMING_LOG.md`
- 更早主线“独立后台下载完成轮询剩余少量回归与验证收口”已完成；详细台账继续只看 `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 更早主线“Feishu 私聊事件解析器去重”已完成；详细台账继续只看 `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线“Feishu 长连接私有 API 风险收口”已完成；详细台账继续只看 `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线“持久化吞错收口”已完成；详细台账继续只看 `docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## 2. Risk groups

### 2.1 query 解析 / TMDB 查询 / 搜索请求编排

当前风险：
- `search_media.py` 还把 `parse_movie_query()`、TMDB 命中后的 query 归一化、`_search_candidates_with_logging()` 调用和歧义预判揉在同一文件；这一步只允许把“搜索前查询准备 + 搜索源请求编排”继续收成 helper，不改 clarification / candidate 持久化协议和 shared runtime 入口。
- 这一组只允许动 query 解析、TMDB 命中后的候选 query 排序，以及搜索源失败日志壳，不顺手改候选缓存、澄清状态或回复文案协议。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_search_media.py -k "parse_movie_query or tmdb or search_and_format_with_results or search_backend_failure"`

### 2.2 歧义澄清 / 候选持久化 / 回复格式化

当前风险：
- `search_media.py` 还把 `_set_clarification_pending()` / `_clear_clarification_pending()`、candidate 持久化与回滚、`format_movie_query_reply()` / `format_bt_read_only_reply()` 混在同一文件；这一步只允许按一组连贯 helper 拆开，不能顺手改 clarification、candidate 和 SQLite 真相边界。
- 这一组继续守住“候选和澄清状态写入失败直接 fail-closed 返回中文提示”的边界，不回退现有 `CANDIDATE_STATE_UNAVAILABLE_TEXT` / `CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT` / `CLARIFICATION_CLEAR_STATE_UNAVAILABLE_TEXT` 协议。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_search_media.py -k "clarification or candidate or quality_from_title"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_search_media.py -k "parse_movie_query or tmdb or search_and_format_with_results or search_backend_failure"`
- `.venv/bin/python -m pytest -q tests/test_search_media.py -k "clarification or candidate or quality_from_title"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.2 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 当前唯一主线已经切到 `docs/SEARCH_MEDIA_SLIMMING_LOG.md`；`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md` 只继续保留完成态路径和 focused tests 入口。
