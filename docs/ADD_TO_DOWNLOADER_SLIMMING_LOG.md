# Add to downloader slimming log (v2)

> 目的：承接当前“`add_to_downloader.py` 下载编排层瘦身 / 模块化”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Completed line

- 已完成主线：`add_to_downloader.py` 下载编排层瘦身 / 模块化（已在 2026-04-19 满足 `Done when` 第 1 条：`app/services/add_pending_context.py` 已承接候选选择 / 来源解析 / 待确认上下文边界，且 focused tests `21 passed, 88 deselected`）
- 上一条已完成主线“`import_to_library.py` 导入编排层瘦身 / 模块化”已在 2026-04-19 满足退出条件 1；详细台账继续只看 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`
- 更早已完成主线“`telegram_bot.py` 渠道层瘦身 / 模块化”已在 2026-04-19 满足退出条件 1；详细台账继续只看 `docs/TELEGRAM_BOT_SLIMMING_LOG.md`
- 更早主线“独立后台下载完成轮询剩余少量回归与验证收口”已完成；详细台账继续只看 `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 更早主线“Feishu 私聊事件解析器去重”已完成；详细台账继续只看 `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线“Feishu 长连接私有 API 风险收口”已完成；详细台账继续只看 `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线“持久化吞错收口”已完成；详细台账继续只看 `docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## 2. Risk groups

### 2.1 候选选择 / 来源解析 / 待确认写入

本轮收口：
- `app/services/add_pending_context.py` 现在承接候选选择、来源解析、BT source task_ref 生成、待确认上下文构建和 payload 序列化；`add_to_downloader.py` 只保留待确认持久化壳、confirm 执行和中文日志，不回退 approval、`jobs` 和下载副作用边界。
- 这一组收口只动下载前真相准备边界；待确认审批写入、pending job 落盘和现有 fail-closed 中文提示协议保持不变。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "add_by_selection or add_candidate_source or record_pending_approval or record_pending_job"`

### 2.2 confirm 执行 / 下载监控登记 / 事件落盘

当前主线：
- `add_to_downloader.py` 里 confirm 上下文重建、lease 抢占、下载器投递、下载监控登记和事件落盘仍在同一文件；当前唯一主线已经切回这一组，优先看是否能抽出 confirm 执行 / monitor / event helper。
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
- 当前唯一主线已经切回 2.2 风险组；本文件继续承接 downloader confirm / monitor / event 相关瘦身闭环，不回到 `search_media.py`。
