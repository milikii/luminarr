# Current status (v464)

## Current mainline

- **质量硬化**、**搜索相关性优化**、**字幕闭环补齐** 与 **刮削系统基础收口** 当前都已收工；默认分支当前保持完成态，若继续推进，优先从 `docs/SCRAPING_SYSTEM_PLAN.md` 的后续 backlog 里选更小闭环。
- 当前这轮已经先把刮削输入真相落稳：`media_identity` 已能沿着 `search -> select -> confirm download -> job_event -> import metadata` 进入导入后处理。
- 当前这一轮又前推一格：只要 `media_identity` 里已有 `tmdb_id`，`metadata_scraper.py` 现在会直接按该 ID 取详情，不再默认走 `search_movie(title, year)` 二次猜片。
- 当前这一轮再补一格：`.metadata.json` 之外的最小本地刮削产物 `.nfo` 已开始落地；文件型目标会写同名 `.nfo`，目录型目标会优先写到主视频旁边。
- 当前这一轮又前推一格：本地 `poster` / `backdrop` 图片产物也已开始落地；文件型目标会写 `<basename>-poster.*` / `<basename>-backdrop.*`，目录型目标会写 `poster.*` / `backdrop.*`。
- 当前这一轮再补一格：刮削写入策略也已明确；`.metadata.json` 默认 `overwrite`，`.nfo` 与图片默认 `missing-only`，没有来源时显式 `skip`。
- 当前这一轮再补最后一格：真实 `import -> scrape -> subtitle -> refresh` smoke 已通过；目标路径 `/data/library/movies/luminarr-real-smoke-1777048577.mkv` 在 Emby 中已返回 `Name=Interstellar`、`Tmdb=157336`。
- 当前这一轮又补了一格中文真相：同样的真实链路在目标路径 `/data/library/movies/luminarr-real-smoke-1777049632.mkv` 上已确认 Emby 返回 `Name=星际穿越`、`Tmdb=157336`；当前本地刮削最终展示已优先中文，不再落英文片名。
- 当前又从刮削后续 backlog 收掉一小格：`ffmpeg` fallback 的结果解析与错误映射也已下沉到 `subtitle_translation_support.py`，并补了“`ffprobe` 缺失且 `ffmpeg` 也缺失时返回明确失败结果”的 focused 护栏。当前 `subtitle_translator.py` 为 `503` 行。
- 首版发布矩阵继续冻结为：Telegram 私聊 + PT Transmission + Emby + movie-first 主链。
- 三座大山保持完成态：`app/services/search_media.py` `568` 行，`add_to_downloader.py` `574` 行，`import_to_library.py` `585` 行。

## Current health

- 仓库级质量入口保持可用：`make quality`、`make verify-mainline`、`make verify-quality-gates` 当前都可复验。
- 搜索链当前保持完成态：续作/章节别名归一、尾部版本噪音剥离、TMDB 高置信长标题命中，以及 `AMZN / DSNP / 4K / 2160p` 这类 BT 标题噪音与等价分辨率去重都已收口。
- 字幕链当前保持完成态：外挂字幕随导入落库、已有中文字幕跳过翻译、无外挂字幕时可探测/提取英文文本字幕再翻译。
- 当前刮削系统的输入真相已经收口：metadata 刮削现在优先消费已确认媒体身份，且有 `tmdb_id` 时会直连详情。
- 当前刮削系统基础收口已完成：`.metadata.json` + `.nfo` + `poster` / `backdrop` 与写入策略都已落地，且真实 `import -> scrape -> subtitle -> refresh` 联调已拿到 Emby 消费证据。
- 当前 live smoke 真相仍分两段：`search -> select -> confirm -> status` 已在真实 Prowlarr / PT Transmission 跑通；`status -> import -> confirm -> refresh` 已在真实 PT Transmission / Emby 跑通。

## Latest verification

- `make quality`：通过；docs/tests 阶段 `28 passed`
- `make verify-mainline`：通过
- `make verify-quality-gates`：通过
- `make test`：`1761 passed, 2 skipped`
- metadata / import / tmdb focused：`.venv/bin/python -m pytest -q tests/test_tmdb_client.py tests/test_metadata_scraper.py tests/test_import_to_library.py tests/test_main.py` 为 `201 passed, 4 warnings`
- 搜索 focused：`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_bt_candidate_scorer.py` 为 `196 passed`
- 搜索 + TMDB focused：`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_tmdb_client.py` 为 `182 passed`
- 字幕 focused：`.venv/bin/python -m pytest -q tests/test_subtitle_translator.py` 为 `37 passed`
- 导入侧字幕 focused：`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k subtitle` 为 `4 passed, 145 deselected`
- 当前真实 smoke 证据仍有效：前半段 `task_id=17` / `task_hash=1ea022ed0c3cbe9139469a8a58f5bfcfaa1875de` 可再次进入 `status`；后半段 `task_ref=d8f737c1468646c8ab35279fa10f89f89e88428e` 可再次进入 `import_by_task_ref -> pending approval -> import.succeeded -> refresh.succeeded`。
- 当前刮削真实 smoke 新证据：`/tmp/luminarr-real-smoke-1777048577.json` 记录了 `metadata_path`、`nfo_path`、`poster_path`、`backdrop_path` 与 Emby 返回的 `Name=Interstellar`、`Tmdb=157336`。
- 当前刮削中文 smoke 新证据：最新样本的 `.metadata.json` 与 `.nfo` 已写入 `title=星际穿越`、`original_title=Interstellar`，Emby 对应媒体项也已返回 `Name=星际穿越`、`Tmdb=157336`。

## Current biggest risk

- 当前最大刮削风险已经从“导入后重新猜片”切到“后续扩展边界”：如果继续往更多图片类型或更复杂命名规则扩，会重新拉高回归风险。
- 当前机器环境真相要继续按当轮探针写；涉及内嵌字幕探测时，默认要求 `ffmpeg` 在 PATH 中可执行。
- 当前最大发布前不确定性已收缩到“下一条主线该从哪个 backlog 入口继续收口”，而不是当前主链是否成立。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
