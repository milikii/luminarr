# Add to downloader slimming log (v10)

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
- `add_to_downloader.py` 里 confirm 上下文重建、lease 抢占、下载器投递、下载监控登记和事件落盘原本混在同一文件；这一组当前唯一主线已经推进到 pending context / trace wrapper，优先看壳文件里剩余的状态辅助和日志辅助是否还能继续抽走。
- 这一组继续守住“下载器已投递是真相；后续监控/事件写入失败只记显式中文日志 + `[处理建议]`，不回滚既有下载副作用”的边界。
- `app/services/add_execution_follow_up.py` 已承接下载器投递、`job_event` 追加、`download_monitor` 登记和成功/失败回复拼装；`add_to_downloader.py` 只保留 confirm 编排、approval/jobs 顺序控制和最终版号/完成态回写，不回退下载副作用真相。
- 这一步把 `add_to_downloader.py` 从 `1669` 行降到 `1549` 行；`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "rebuild_confirm_context or claim_pending_job or confirm_add_by_task_ref or register_download_monitor or record_event"` 为 `40 passed, 71 deselected`，`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py` 为 `111 passed`，`make quality` 为 `24 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1716 passed, 4 warnings`。
- `app/services/add_cancel_state.py` 已承接 `cancel_pending_add()` 的 pending lookup / lease / approval+job cancel / fail-closed 中文日志；`add_to_downloader.py` 只保留 public cancel 入口 wrapper，不回退取消协议、SQLite 真相或 `job_event(downloader.cancelled)` 边界。
- 这一步把 `add_to_downloader.py` 从 `1549` 行降到 `1399` 行；`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "cancel_pending_add or cancel_pending_approval or handle_expired_pending_confirm"` 为 `19 passed, 92 deselected`，`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py` 继续 `111 passed`，`make quality` 继续 `24 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1716 passed, 4 warnings`。
- `app/services/add_confirm_job_state.py` 已承接 confirm jobs 抢占 / 回退 / 完结和 lease owner helper；`add_to_downloader.py` 只保留 confirm 编排、approval/lease 判定和下载副作用顺序控制，不回退 jobs 状态机中文 fail-closed 日志。
- 这一步把 `add_to_downloader.py` 从 `1399` 行降到 `1315` 行；`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "rebuild_confirm_context or claim_pending_job or confirm_add_by_task_ref or handle_expired_pending_confirm"` 为 `38 passed, 73 deselected`，`make quality` 为 `24 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1716 passed, 4 warnings`。
- `app/services/add_confirm_approval_state.py` 已承接 approval / lease 查询、stale-check 和 pending expiry helper；`add_to_downloader.py` 只保留 confirm 上下文重建、approval 写入 wrapper 和过期后 cancel/event 收口，不回退 approval/lease 中文 fail-closed 日志。
- 这一步把 `add_to_downloader.py` 从 `1315` 行降到 `1235` 行；`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "rebuild_confirm_context or claim_pending_job or confirm_add_by_task_ref or handle_expired_pending_confirm or resolve_pending_lease_version or stale_rejection or pending_approval_expired"` 为 `46 passed, 65 deselected`，`make quality` 为 `24 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1716 passed, 4 warnings`。
- `app/services/add_confirm_context_state.py` 已承接 confirm context rebuild、approval 查询和 expired confirm 的 approval+job cancel/event 收口；`add_to_downloader.py` 只保留 confirm 编排顺序、approval 写入 wrapper、jobs 状态机 wrapper 和最终版号/完成态回写，不回退中文 fail-closed 日志。
- 这一步把 `add_to_downloader.py` 从 `1235` 行降到 `1117` 行；`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "rebuild_confirm_context or claim_pending_job or confirm_add_by_task_ref or handle_expired_pending_confirm or resolve_pending_lease_version or stale_rejection or pending_approval_expired"` 继续 `46 passed, 65 deselected`，`make quality` 为 `24 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1716 passed, 4 warnings`，真实 `add_to_downloader confirm` smoke 也已通过。
- `app/services/add_confirm_approval_state.py` 已继续承接 pending approval 写入 / approve / restore / cancel / executed-version 回写；`add_to_downloader.py` 只保留 confirm 编排顺序、approval identity move、finalization warning 汇总和最外层 pending 持久化壳，不回退 approval/lease 中文 fail-closed 日志。
- 这一步把 `add_to_downloader.py` 从 `1117` 行降到 `937` 行；`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py` 为 `111 passed`，`make quality` 为 `24 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1716 passed, 4 warnings`，真实 `add_to_downloader confirm` smoke 继续通过。
- `app/services/add_confirm_approval_state.py` 已继续承接 approval identity move；`tests/test_add_to_downloader.py` 补了 identity move 失败时的 finalization warning guard，`add_to_downloader.py` 只保留 finalization warning 汇总、job completion 尾部回写、pending context 清理和 trace wrapper，不回退 warning 协议。
- 这一步把 `add_to_downloader.py` 从 `937` 行降到 `927` 行；`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py` 为 `113 passed`，`make quality` 为 `24 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1718 passed, 4 warnings`，真实 `add_to_downloader confirm` smoke 继续通过。
- `app/services/add_confirm_finalization_state.py` 已承接 confirm 成功后的 finalization warning 汇总、job completion 尾部回写、pending context 清理和 finalize trace；`add_to_downloader.py` 只保留入口壳、pending context/trace wrapper 和最外层 helper 顺序控制，不回退 warning 文本或 trace 协议。
- 这一步把 `add_to_downloader.py` 从 `927` 行降到 `892` 行；`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py` 继续 `113 passed`，`make quality` 为 `24 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1718 passed, 4 warnings`，真实 `add_to_downloader confirm` smoke 继续通过。
- `app/services/add_pending_context.py` 已继续承接进程内 pending context 记录 / 查询 / 清理 / 缺失日志 helper；`add_to_downloader.py` 只保留 pending runtime state 的最外层调用、不再直接持有两张进程内字典和整段缺失日志分支，不回退下载确认 fail-closed 中文日志协议。
- 这一步把 `add_to_downloader.py` 从 `892` 行降到 `866` 行；`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py` 继续 `113 passed`，`make quality` 为 `24 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1718 passed, 4 warnings`，真实 `add_to_downloader confirm` smoke 也已再次通过。
- `app/services/add_trace_logger.py` 已承接下载链 pure trace wrapper；`add_to_downloader.py` 只保留 trace helper 注入和 pending trace 调用，不再直接持有 `_log_trace()` 这组固定协议包装，不回退 trace 字段或落盘协议。
- 这一步把 `add_to_downloader.py` 从 `866` 行降到 `838` 行；`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py` 继续 `113 passed`，`make quality` 为 `24 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1718 passed, 4 warnings`，真实 `add_to_downloader confirm` smoke 也已再次通过。
- `app/services/add_pending_persistence.py` 已承接 pending job 落盘失败分流和待确认回复渲染；`add_to_downloader.py` 只保留 pending approval -> in-memory context -> event/trace -> reply 的最外层顺序控制，不再直接持有 jobs 待确认落盘长分支和 delivery item 渲染，不回退待确认文本协议。
- 这一步把 `add_to_downloader.py` 从 `838` 行降到 `787` 行；`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py` 继续 `113 passed`，`make quality` 为 `24 passed`，全量 `.venv/bin/python -m pytest -q` 继续 `1718 passed, 4 warnings`，真实 `add_to_downloader confirm` smoke 也已再次通过。

剩余风险：
- `add_to_downloader.py` 还把 add request 入口壳和大块 confirm 编排壳混在主文件里；下一步只允许优先评估 `add_by_selection()`、`add_by_batch_selection()`、`add_candidate_source()`、`add_bt_source()` 这组入口 facade，不顺手改 downloader dispatch、jobs 状态机或下载回复协议。
- 这一组继续守住“下载器已投递是真相；approval / jobs / lease 读取失败直接 fail-closed 返回中文提示”的边界，不回退 `ADD_CONFIRM_STATE_UNAVAILABLE_TEXT` / `ADD_CONFIRM_NOT_PENDING_TEXT` / `ADD_CONFIRM_EXPIRED_TEXT` 协议。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_add_to_downloader.py`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "add_by_selection or add_candidate_source or record_pending_approval or record_pending_job"`
- `.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "rebuild_confirm_context or claim_pending_job or confirm_add_by_task_ref or register_download_monitor or record_event"`
- `.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "cancel_pending_add or cancel_pending_approval or handle_expired_pending_confirm"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.2 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 当前唯一主线已经切回 2.2 风险组；本文件继续承接 downloader confirm 相关瘦身闭环，不回到 `docs/SEARCH_MEDIA_SLIMMING_LOG.md`。
