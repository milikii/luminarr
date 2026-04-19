# Series anime naming log (v4)

> 目的：承接当前“`series / anime` 独立名称解析最小实现（含 `.ass` 最小支持评估）”主线的详细台账。
> 约束：蓝图看 `docs/SERIES_ANIME_NAMING_PLAN.md`；`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 当前主线状态：2026-04-19 已在 `app/main.py` 主线完成后切入，并在同日通过 `_extract_title_year_for_scrape()` 接入统一 parser + focused suite `245 passed` 满足 `Done when` 第 1 条；当前唯一主线已切到 `docs/SHARED_DELIVERY_UX_PLAN.md`
- 上一条已完成主线“`app/main.py` 启动装配 / 下载器路由 helper 瘦身 / 模块化”已在 2026-04-19 通过 `app/downloader_route_lookup.py` helper 抽离满足 `Done when` 第 1 条，focused tests `16 passed, 1 deselected`
- 当前这一步的设计蓝图、Phase 顺序和退出条件统一看 `docs/SERIES_ANIME_NAMING_PLAN.md`

## 2. Risk groups

### 2.1 统一解析结构

已完成闭环：
- 已新增 `app/services/media_name_parser.py`，先把用户文本 / 候选标题 / 文件名会共用的最小输出结构 `ParsedMediaName` 和 Phase 1 内置解析规则落地；当前先不切四处集成点。
- 已新增 `tests/test_media_name_parser.py` 10 条典型输入回归，覆盖年份、`S01E01`、`第2季`、方括号集号、发布组、画质标签、容器和中英混合标题。
- 已新增 `app/services/naming_rules.yml` 和 parser 内的可选规则加载：现在可从静态文件补 `strip_tags`、`alt_titles`、`quality_whitelist`，文件缺失或格式错误时自动回退内置最小集。
- 已把 `tests/test_media_name_parser.py` 扩到 15 条回归，覆盖 repo 规则文件生效、别名补全、自定义质量标签和缺文件 fallback。

当前风险：
- 当前主线已完成；后续若要继续扩 parser 规则或补 `.ass`，应另立闭环，不要回退已达成的 Phase 1-3 最小出口。

### 2.2 四处集成点切换

已完成闭环：
- 已把 `search_request_context.parse_movie_query()` 切到 `media_name_parser`，查询标题会先剥离季集噪音，再保留现有 `ParsedMovieQuery(title, year)` 出口。
- 已把 `bt_sources.normalize_bt_candidate()` 接到统一 parser，候选结果现在会额外带 `parsedMediaName` 供后续 Phase 3 / Phase 4 继续消费，不回退现有展示标题和去重键。
- 已把 `import_to_library` 里的导入命名 helper 和 metadata 标题提取 helper 接到统一 parser，但电影命名仍保留原有格式化逻辑，避免这一步把 movie-first 行为改坏。

已完成闭环：
- 已把 `import_to_library._extract_title_year_for_scrape()` 的下载完成文件名 fallback 也切到统一 parser；当 job_event 里暂时没有稳定命名真相时，metadata scraping 仍会先从统一 `ParsedMediaName` 提取标题。
- 已新增 `tests/test_import_to_library.py` 回归，覆盖 `S01E01` 文件名和 `[SweetSub][Frieren][01]` 目录名 fallback 进入 TMDB 标题提取。
- 已跑通 Phase 3 focused suite：`.venv/bin/python -m pytest -q tests/test_media_name_parser.py tests/test_search_media.py tests/test_import_to_library.py tests/test_get_download_status.py tests/test_subtitle_translator.py` 得到 `245 passed`。

当前风险：
- 当前主线已通过 `Done when` 第 1 条完成；后续若补 `.ass` 或 clarification 分流，应按新主线优先级另开闭环，不在已完成主线上继续堆改动。

### 2.3 `.ass` 最小支持

当前风险：
- 当前字幕翻译只处理 `.srt`；动漫主线落地时必须同步评估 `.ass`，但只允许做最小文本替换，不扩大到嵌入字幕或复杂样式改写。

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_media_name_parser.py`
- `.venv/bin/python -m pytest -q tests/test_media_name_parser.py`（当前 15 条）
- `.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_bt_sources.py tests/test_import_to_library.py`
- `.venv/bin/python -m pytest -q tests/test_media_name_parser.py tests/test_search_media.py tests/test_import_to_library.py tests/test_get_download_status.py tests/test_subtitle_translator.py`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 新闭环优先按 2.1~2.3 合并；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 当前主线完成后，在 `docs/NEXT_STEP.md`、`docs/STATUS.md`、`README.md` 和 `AGENTS.md` 同步切到下一项。
