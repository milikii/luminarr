# Current status (v454)

## Current mainline

- **质量硬化**、**搜索相关性优化** 与 **字幕闭环补齐** 当前都已收工；当前主线切到 **刮削系统基础收口**。
- 当前这轮先补的不是 NFO/海报，而是刮削输入真相：把已确认的 `media_identity` 沿着 `search -> select -> confirm download -> job_event -> import metadata` 落稳。
- 这样做的目标很明确：metadata 刮削不再默认靠文件名重新猜片，后续 `.metadata.json` / `.nfo` / 本地图片都先基于这份真相推进。
- 首版发布矩阵继续冻结为：Telegram 私聊 + PT Transmission + Emby + movie-first 主链。
- 三座大山保持完成态：`app/services/search_media.py` `568` 行，`add_to_downloader.py` `574` 行，`import_to_library.py` `585` 行。

## Current health

- 仓库级质量入口保持可用：`make quality`、`make verify-mainline`、`make verify-quality-gates` 当前都可复验。
- 搜索链当前保持完成态：续作/章节别名归一、尾部版本噪音剥离、TMDB 高置信长标题命中，以及 `AMZN / DSNP / 4K / 2160p` 这类 BT 标题噪音与等价分辨率去重都已收口。
- 字幕链当前保持完成态：外挂字幕随导入落库、已有中文字幕跳过翻译、无外挂字幕时可探测/提取英文文本字幕再翻译。
- 当前刮削系统的最大缺口已经收缩到一个点：`metadata_scraper.py` 还在默认靠 `title/year` 再猜一次 TMDB，而不是优先消费主链里已经确认过的媒体身份。
- 当前 live smoke 真相仍分两段：`search -> select -> confirm -> status` 已在真实 Prowlarr / PT Transmission 跑通；`status -> import -> confirm -> refresh` 已在真实 PT Transmission / Emby 跑通。

## Latest verification

- `make quality`：通过；docs/tests 阶段 `28 passed`
- `make verify-mainline`：通过
- `make verify-quality-gates`：通过
- `make test`：`1761 passed, 2 skipped`
- 搜索 focused：`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_bt_candidate_scorer.py` 为 `196 passed`
- 搜索 + TMDB focused：`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_tmdb_client.py` 为 `182 passed`
- 字幕 / 导入 focused：`.venv/bin/python -m pytest -q tests/test_subtitle_translator.py tests/test_import_to_library.py` 为 `161 passed`
- 当前真实 smoke 证据仍有效：前半段 `task_id=17` / `task_hash=1ea022ed0c3cbe9139469a8a58f5bfcfaa1875de` 可再次进入 `status`；后半段 `task_ref=d8f737c1468646c8ab35279fa10f89f89e88428e` 可再次进入 `import_by_task_ref -> pending approval -> import.succeeded -> refresh.succeeded`。

## Current biggest risk

- 当前最大刮削风险不是图片少，而是“导入后重新猜片”：只要 `media_identity` 没落稳，后续 `.metadata.json` / `.nfo` / 本地图片都可能围绕错误媒体对象展开。
- 当前机器环境真相要继续按当轮探针写；涉及内嵌字幕探测时，默认要求 `ffmpeg` 在 PATH 中可执行。
- 当前最大发布前不确定性已从“搜索第一屏排序”切到“刮削输入真相边界”；这条主线当前应该优先做真相收口，而不是再开新的元数据 provider 支线。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
