# Series anime naming log (v2)

> 目的：承接当前“`series / anime` 独立名称解析最小实现（含 `.ass` 最小支持评估）”主线的详细台账。
> 约束：蓝图看 `docs/SERIES_ANIME_NAMING_PLAN.md`；`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 当前主线状态：2026-04-19 已在 `app/main.py` 主线完成后正式切到 `series / anime` 独立名称解析最小实现
- 上一条已完成主线“`app/main.py` 启动装配 / 下载器路由 helper 瘦身 / 模块化”已在 2026-04-19 通过 `app/downloader_route_lookup.py` helper 抽离满足 `Done when` 第 1 条，focused tests `16 passed, 1 deselected`
- 当前这一步的设计蓝图、Phase 顺序和退出条件统一看 `docs/SERIES_ANIME_NAMING_PLAN.md`

## 2. Risk groups

### 2.1 统一解析结构

已完成闭环：
- 已新增 `app/services/media_name_parser.py`，先把用户文本 / 候选标题 / 文件名会共用的最小输出结构 `ParsedMediaName` 和 Phase 1 内置解析规则落地；当前先不切四处集成点。
- 已新增 `tests/test_media_name_parser.py` 10 条典型输入回归，覆盖年份、`S01E01`、`第2季`、方括号集号、发布组、画质标签、容器和中英混合标题。

当前风险：
- Phase 1 只落了内置最小集；跨语言别名、噪音词裁剪和后续四处集成点切换还没做，TMDB 关联、追更和导入命名暂时仍没真正共用这一结构。

### 2.2 四处集成点切换

当前风险：
- `search_media`、BT source adapter、`post_download_auto_import`、`import_to_library` 还没统一读同一个 `ParsedMediaName`；切换时必须守住现有 movie-first 行为不回退。

### 2.3 `.ass` 最小支持

当前风险：
- 当前字幕翻译只处理 `.srt`；动漫主线落地时必须同步评估 `.ass`，但只允许做最小文本替换，不扩大到嵌入字幕或复杂样式改写。

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_media_name_parser.py`
- `.venv/bin/python -m pytest -q tests/test_media_name_parser.py tests/test_search_media.py tests/test_import_to_library.py tests/test_post_download_auto_import.py tests/test_subtitle_translator.py`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 新闭环优先按 2.1~2.3 合并；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 当前主线完成后，在 `docs/NEXT_STEP.md`、`docs/STATUS.md`、`README.md` 和 `AGENTS.md` 同步切到下一项。
