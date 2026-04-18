# Add to downloader slimming log (v1)

> 目的：承接当前“`add_to_downloader.py` 下载编排层瘦身 / 模块化”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 当前唯一主线：`add_to_downloader.py` 下载编排层瘦身 / 模块化
- 上一条已完成主线“`import_to_library.py` 导入编排层瘦身 / 模块化”已在 2026-04-19 满足退出条件 1；详细台账继续只看 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`
- 更早已完成主线“`telegram_bot.py` 渠道层瘦身 / 模块化”已在 2026-04-19 满足退出条件 1；详细台账继续只看 `docs/TELEGRAM_BOT_SLIMMING_LOG.md`
- 更早主线“独立后台下载完成轮询剩余少量回归与验证收口”已完成；详细台账继续只看 `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 更早主线“Feishu 私聊事件解析器去重”已完成；详细台账继续只看 `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线“Feishu 长连接私有 API 风险收口”已完成；详细台账继续只看 `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线“持久化吞错收口”已完成；详细台账继续只看 `docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## 2. Risk groups

### 2.1 候选选择 / 来源解析 / 待确认写入

当前风险：
- `add_to_downloader.py` 仍把候选选择、来源解析、待确认审批写入和 pending job 落盘揉在同一文件；这一步只允许把这一组“下载前真相准备 + fail-closed 停路”继续收成更小 helper，不改 search、approval、`jobs` 和下载副作用边界。
- 这一组只允许动 `add_by_selection()` / `add_candidate_source()` 前半段和 pending 持久化壳，不顺手改 confirm、下载监控登记或事件落盘协议。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "add_by_selection or add_candidate_source or record_pending_approval or record_pending_job"`

### 2.2 confirm 执行 / 下载监控登记 / 事件落盘

当前风险：
- `add_to_downloader.py` 还把 confirm 上下文重建、lease 抢占、下载器投递、下载监控登记和事件落盘混在同一文件；这一步只允许按一组连贯 helper 拆开，不能顺手改 downloader client、`download_monitor`、`job_event` 或已投递下载真相。
- 这一组继续守住“下载器已投递是真相；后续监控/事件写入失败只记显式中文日志 + `[处理建议]`，不回滚既有下载副作用”的边界。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "rebuild_confirm_context or claim_pending_job or confirm_add_by_task_ref or register_download_monitor or record_event"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "add_by_selection or add_candidate_source or record_pending_approval or record_pending_job"`
- `.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "rebuild_confirm_context or claim_pending_job or confirm_add_by_task_ref or register_download_monitor or record_event"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.2 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 只有当当前主线完成并切到下一项时，才在 `docs/NEXT_STEP.md` 和 `README.md` 切换“当前唯一主线”。
