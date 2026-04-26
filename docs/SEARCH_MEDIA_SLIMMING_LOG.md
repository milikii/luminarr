# Search media slimming log (v5)

> 目的：承接当前“`search_media.py` 搜索编排层瘦身 / 模块化”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Completed line

- 已完成主线：`search_media.py` 搜索编排层瘦身 / 模块化（已在 2026-04-19 满足 `Done when` 第 1 条：`app/services/search_request_context.py` 已承接 query 解析 / TMDB 查询 / 搜索请求编排边界，且 focused tests `12 passed, 27 deselected`）
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

本轮收口：
- `app/services/search_request_context.py` 现在承接 `parse_movie_query()`、TMDB 命中后的 query 归一化、候选 query 排序和搜索源失败日志壳；`search_media.py` 只保留澄清态、候选持久化、回复格式化和现有 fail-closed 中文协议。
- 这一组收口只动搜索前半段边界；clarification、candidate 和 shared runtime 入口未改。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_search_media.py -k "parse_movie_query or tmdb or search_and_format_with_results or search_backend_failure"`

### 2.2 歧义澄清 / 候选持久化 / 回复格式化

本轮收口：
- `app/services/search_reply_formatter.py` 现在承接 `normalize_candidate()`、movie reply / delivery item、BT 只读与批量预览回复、标题质量猜测和共享格式化字段；`search_media.py` 已从 `1018` 行降到 `725` 行。
- 这一组收口只动回复协议和共享字段格式化；clarification、candidate 和 SQLite 真相边界未改。
- `app/services/search_clarification_state.py` 现在承接 clarification pending / clear / persisted load 与 fail-closed 中文日志；`search_media.py` 已从 `725` 行降到 `616` 行。
- 这一组继续只动澄清态读写边界；candidate 持久化和搜索文本协议未改。
- `app/services/search_candidate_state.py` 现在承接 candidate save / load / rollback、批量预览候选缓存和对应 fail-closed 中文日志；`search_media.py` 已从 `616` 行降到 `460` 行。
- 这一组继续只动候选状态真相边界；搜索排序、BT 预览协议和回复文本协议未改。
- `app/services/bt_read_only_display.py` 现在承接 BT 只读候选注释 / helper 贴标 / 历史提示；`search_media.py` 当前回到 `627` 行。
- 这一轮只把成熟的展示分支和 helper lookup 从热文件里抽走，未改 `bt搜` / `bt批量` 对外协议和 helper 真相边界。
- `app/services/search_ambiguity_helper.py` 已承接歧义澄清 helper；`app/services/search_media_bt_ordering.py` 已承接 media-BT 排序 helper；`search_media.py` 已降到 `313` 行。
- 当前主线已重新切回本文件；下一组只动 `search_media.py` 里剩余的 batch preview 页面支持 helper，不回退 clarification / candidate / read-only truth。

剩余风险：
- `search_media.py` 当前回到 `313` 行，已比最初基线明显收口，但仍高于纯粹编排层的理想尺寸；下一步若继续瘦身，应优先沿 `search_request_context.py` / `search_reply_formatter.py` / `bt_read_only_display.py` / `search_ambiguity_helper.py` / `search_media_bt_ordering.py` 的既有边界继续拆，不要再把成熟的展示逻辑塞回主文件。
- 搜索链继续守住“候选和澄清状态写入失败直接 fail-closed 返回中文提示”的边界，不回退现有 `CANDIDATE_STATE_UNAVAILABLE_TEXT` / `CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT` / `CLARIFICATION_CLEAR_STATE_UNAVAILABLE_TEXT` 协议。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_search_media.py -k "clarification or candidate or quality_from_title"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_search_media.py -k "parse_movie_query or tmdb or search_and_format_with_results or search_backend_failure"`
- `.venv/bin/python -m pytest -q tests/test_search_media.py -k "clarification or candidate or quality_from_title"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.2 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 当前唯一主线已经重新切回本文件；新的最小闭环继续优先并入 2.2 的 media-BT 排序 / batch preview helper 风险组，不回到 `manage_bt_subscription.py`。
