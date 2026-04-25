# Current status (v466)

## Current mainline

- **质量硬化**、**搜索相关性优化**、**字幕闭环补齐** 与 **刮削系统基础收口** 当前都已完成；默认分支继续推进时，优先从 `docs/SCRAPING_SYSTEM_PLAN.md` 的后续 backlog 里选更小闭环。
- 刮削主链当前真相已收口：`media_identity` 能沿 `search -> select -> confirm download -> job_event -> import metadata` 落稳；`metadata_scraper.py` 优先吃 `tmdb_id`；`.metadata.json` / `.nfo` / `poster` / `backdrop` 已落地；真实 `import -> scrape -> subtitle -> refresh` smoke 已确认 Emby 返回 `Name=星际穿越`、`Tmdb=157336`。
- 字幕链当前保持完成态：外挂字幕随导入落库；已有中文字幕时跳过翻译；无外挂字幕时可探测/提取英文文本内嵌字幕再翻译。
- 本轮又沿结构 backlog 连续收掉 5 个小闭环：
  - `subtitle_translator.py`：`translate_for_import()` 的前置校验已下沉到 `subtitle_translation_support.py`，统一处理目标存在性、目标字幕解析、API key 缺失与 metadata title 读取；当前 `267` 行。
  - `job_repo.py`：`mark_downloader_completed()` 与 `cancel_pending_job()` 的身份规范化已下沉到 `job_repo_support.py`；当前 `536` 行。
  - `approval_repo.py`：`_approve/_restore_pending/_cancel` 的共享状态迁移薄壳已合并到 helper，且 `_upsert_approval()` / `_request_approval()` 的 SQL 写入边界已下沉到 `approval_repo_support.py`；当前 `715` 行。
- 当前又从 approval backlog 再收掉一小格：`_mark_executed()` 的身份规范化也已下沉到 `approval_repo_support.py`，`approval_repo.py` 当前为 `714` 行。
- 当前又从 approval backlog 再收掉一小格：多处重复的 exact-record 缺失判定已收口到 `_require_exact_approval_record()`，`approval_repo.py` 当前为 `726` 行。
- 当前又从 job backlog 再收掉一小格：chat + task_ref 查询身份已收口到 `job_repo_support.py`，`get_pending_job_for_chat_ref()` / `get_job_for_chat_ref()` / `_get_job_for_chat_ref()` 现在共用同一组 query identity helper。
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
- 2026-04-25 subtitle 前置校验收口：`.venv/bin/python -m pyflakes app/services/subtitle_translator.py app/services/subtitle_translation_support.py tests/test_subtitle_translator.py` 通过；`.venv/bin/python -m pytest -q tests/test_subtitle_translator.py` 为 `38 passed`。
- 2026-04-25 job identity 收口：`.venv/bin/python -m pyflakes app/db/job_repo.py app/db/job_repo_support.py` 通过；两组 focused 结果分别为 `2 passed, 109 deselected` 与 `4 passed, 107 deselected`。
- 2026-04-25 approval helper / SQL 收口：`.venv/bin/python -m pyflakes app/db/approval_repo.py app/db/approval_repo_support.py` 通过；三组 focused 结果分别为 `5 passed, 106 deselected`、`3 passed, 108 deselected`、`3 passed, 108 deselected`。
- 2026-04-25 approval executed identity follow-up：`.venv/bin/python -m pyflakes app/db/approval_repo.py app/db/approval_repo_support.py` 通过；`.venv/bin/python -m pytest -q tests/test_persistence_sqlite.py -k "approval_repo_rejects_missing_identity_for_write_paths or approval_repo_raises_when_mark_executed_row_missing"` 为 `2 passed, 109 deselected`。
- 2026-04-25 approval exact-record helper follow-up：`.venv/bin/python -m pyflakes app/db/approval_repo.py` 通过；`.venv/bin/python -m pytest -q tests/test_persistence_sqlite.py -k "approval_repo_raises_when_upsert_row_missing or approval_repo_approve_raises_when_row_missing or approval_repo_cancel_raises_when_row_missing or approval_repo_restore_pending_raises_when_row_missing or approval_repo_raises_when_pending_request_row_missing or approval_repo_raises_when_mark_executed_row_missing or approval_repo_raises_when_pending_expiry_row_missing"` 为 `7 passed, 104 deselected`。
- 2026-04-25 job chat-task query helper follow-up：`.venv/bin/python -m pyflakes app/db/job_repo.py app/db/job_repo_support.py` 通过；`.venv/bin/python -m pytest -q tests/test_persistence_sqlite.py -k "job_repo_rejects_missing_identity_for_query or get_job_for_chat_ref or get_pending_job_for_chat_ref"` 为 `1 passed, 110 deselected`。
- 当前真实 smoke 证据仍有效：前半段 `task_id=17` / `task_hash=1ea022ed0c3cbe9139469a8a58f5bfcfaa1875de` 可再次进入 `status`；后半段 `task_ref=d8f737c1468646c8ab35279fa10f89f89e88428e` 可再次进入 `import_by_task_ref -> pending approval -> import.succeeded -> refresh.succeeded`。

## Current biggest risk

- 当前最大不确定性已经不是主链是否成立，而是“下一条更保守的小闭环该优先选 subtitle / approval / job 里的哪一段剩余壳层”。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
