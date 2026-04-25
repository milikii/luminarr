# Current status (v468)

## Current mainline

- **质量硬化**、**搜索相关性优化**、**字幕闭环补齐** 与 **刮削系统基础收口** 当前都已完成；默认分支继续推进时，优先从 `docs/SCRAPING_SYSTEM_PLAN.md` 的后续 backlog 里选更小闭环。
- 刮削主链当前真相已收口：`media_identity` 能沿 `search -> select -> confirm download -> job_event -> import metadata` 落稳；`metadata_scraper.py` 优先吃 `tmdb_id`；`.metadata.json` / `.nfo` / `poster` / `backdrop` 已落地；真实 `import -> scrape -> subtitle -> refresh` smoke 已确认 Emby 返回 `Name=星际穿越`、`Tmdb=157336`。
- 字幕链当前保持完成态：外挂字幕随导入落库；已有中文字幕时跳过翻译；无外挂字幕时可探测/提取英文文本内嵌字幕再翻译。
- approval / job / subtitle backlog 当前保持最近收口态：`approval_repo.py` 的 exact query / lease version / exact-record / executed identity helper 已下沉到 `approval_repo_support.py`；`job_repo.py` 的 chat-task / workflow / latest pending query、require-by-identity 与 pending upsert 回读边界已下沉到 `job_repo_support.py`；`subtitle_translator.py` 的前置校验与统一 result builder 已下沉到 helper。当前 `approval_repo.py` `749` 行、`job_repo.py` `541` 行、`subtitle_translator.py` `274` 行。
- BT subscription backlog：`scan result` / `scheduler tick` / `last_seen` 回写三段噪声分支已下沉到 `bt_subscription_scan_support.py` / `bt_subscription_scheduler_support.py` / `bt_subscription_last_seen_support.py`；`manage_bt_subscription.py` 当前为 `824` 行。
- 首版发布矩阵继续冻结为：Telegram 私聊 + PT Transmission + Emby + movie-first 主链。
- 三座大山保持完成态：`app/services/search_media.py` `568` 行，`add_to_downloader.py` `574` 行，`import_to_library.py` `585` 行。

## Current health

- 仓库级质量入口保持可复验：`make quality`、`make verify-mainline`、`make verify-quality-gates`。
- 搜索链、字幕链、刮削链当前都保持完成态；当前最大风险仍是后续若继续扩更多图片类型或更复杂命名规则，会重新拉高回归风险。
- 当前机器环境真相保持不变：涉及内嵌字幕探测时，默认要求 `ffmpeg` / `ffprobe` 在 PATH 中可执行。

## Latest verification

- `make verify-quality-gates`：通过
- `make test`：`1761 passed, 2 skipped`
- 2026-04-25 冷启动一致性检查：`make quality`、`make verify-mainline` 与 `.venv/bin/python -m pytest -q tests/test_subtitle_translator.py` 均已复验通过。
- 2026-04-25 approval / job / subtitle follow-up：相关 `pyflakes` 全部通过；approval focused 为 `5 passed, 106 deselected`、`3 passed, 108 deselected`、`3 passed, 108 deselected`、`2 passed, 109 deselected`、`7 passed, 104 deselected`；job focused 为 `2 passed, 109 deselected`、`4 passed, 107 deselected`、`1 passed, 110 deselected`、`1 passed, 110 deselected`、`3 passed, 108 deselected`、`2 passed, 109 deselected`；字幕 focused 为 `38 passed`；当时的 `make quality` 与 `make verify-mainline` 均已通过。
- 2026-04-25 bt subscription scan helper：`.venv/bin/python -m pyflakes app/services/manage_bt_subscription.py app/services/bt_subscription_scan_support.py tests/test_bt_subscription_scan_support.py` 通过；`.venv/bin/python -m pytest -q tests/test_bt_subscription_scan_support.py tests/test_manage_bt_subscription.py -k "bt_subscription_run or bt_subscription_scheduler or bt_subscription_scan_support"` 为 `25 passed, 17 deselected`。
- 2026-04-25 bt subscription scheduler helper：`.venv/bin/python -m pyflakes app/services/manage_bt_subscription.py app/services/bt_subscription_scan_support.py app/services/bt_subscription_scheduler_support.py tests/test_bt_subscription_scheduler_support.py` 通过；`.venv/bin/python -m pytest -q tests/test_bt_subscription_scheduler_support.py tests/test_manage_bt_subscription.py -k "bt_subscription_scheduler"` 为 `12 passed, 29 deselected`。
- 2026-04-25 bt subscription last_seen helper：`.venv/bin/python -m pyflakes app/services/manage_bt_subscription.py app/services/bt_subscription_last_seen_support.py tests/test_bt_subscription_last_seen_support.py` 通过；`.venv/bin/python -m pytest -q tests/test_bt_subscription_last_seen_support.py tests/test_manage_bt_subscription.py -k "last_seen"` 为 `8 passed, 33 deselected`。
- 当前真实 smoke 证据仍有效：前半段 `task_id=17` / `task_hash=1ea022ed0c3cbe9139469a8a58f5bfcfaa1875de` 可再次进入 `status`；后半段 `task_ref=d8f737c1468646c8ab35279fa10f89f89e88428e` 可再次进入 `import_by_task_ref -> pending approval -> import.succeeded -> refresh.succeeded`。

## Current biggest risk

- 当前最大不确定性已经不是主链是否成立，而是“下一条更保守的小闭环该优先选 bt_subscription / subtitle / approval / job 里的哪一段剩余壳层”。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
