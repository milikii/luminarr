# Download completion polling log (v2)

> 目的：承接已完成的“独立后台下载完成轮询剩余少量回归与验证收口”主线详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Completed line

- 已完成主线：独立后台下载完成轮询剩余少量回归与验证收口（已在 2026-04-18 满足 `Done when` 第 1 条：focused tests `12 passed, 141 deselected`，且真实 Transmission / Emby 联调下复用 task_id=`1` task_hash=`e93d696a3e980458765f8016ce39f61437cc9543`，验证其从待轮询列表推进到 `downloader.completed_observed + auto_import boundary`）
- 上一条已完成主线“Feishu 私聊事件解析器去重”已在 2026-04-18 满足退出条件 3；详细台账继续只看 `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线“Feishu 长连接私有 API 风险收口”已完成；详细台账继续只看 `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线“持久化吞错收口”已完成；详细台账继续只看 `docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## 2. Risk groups

### 2.1 待轮询列表读取 / fail-closed 边界

当前风险：
- `_poll_pending_download_completion_once()` 继续依赖 `download_monitor_repo.list_pending_completion()`；结果缺失、记录损坏和普通读取失败都必须维持独立中文日志，且当前轮询不能把这些异常误判成“当前没有待处理任务”。
- 这一组只允许收口待轮询列表读取、日志和 focused verification；不改已投递下载副作用、导入审批真相和 shared runtime。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "pending_list"`

### 2.2 轮询启动 / 停机 / 状态查询边界

当前风险：
- `_download_completion_polling_loop()`、`_start_post_download_auto_import_scheduler()` 和 `_stop_post_download_auto_import_scheduler()` 要继续守住“可独立启动、失败显式日志、停机不吞错”这条边界，即使 `post_download_auto_import_service` 缺席，也不能把下载完成轮询一起带没。
- 这一组允许补真实 Transmission / Emby 联调证据，但只验证既有下载状态观察和自动导入边界，不扩成新的导入编排或 Telegram 渠道层重构。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "download_completion_polling or post_download_auto_import_scheduler"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "pending_list or download_completion_polling or post_download_auto_import_scheduler"`
- `2026-04-18` 真实联调验证：Transmission `task_id=1` `task_hash=e93d696a3e980458765f8016ce39f61437cc9543` 从待轮询列表推进到 `downloader.completed_observed + auto_import boundary`；Emby 健康检查返回 `ServerName=9f4635e04057`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.2 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 当前唯一主线已经切到 `docs/TELEGRAM_BOT_SLIMMING_LOG.md`；本文件只继续保留完成态路径和 focused tests / 联调证据入口。
