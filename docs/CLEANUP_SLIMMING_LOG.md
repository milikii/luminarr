# Cleanup slimming log (v1)

> 目的：承接当前“`cleanup_downloaded_source.py` cleanup 编排层瘦身 / 模块化”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 当前唯一主线：`cleanup_downloaded_source.py` cleanup 编排层瘦身 / 模块化
- 上一条已完成主线“`manage_bt_subscription.py` 订阅编排层瘦身 / 模块化”已在 2026-04-19 满足 `Done when` 第 1 条：`app/services/bt_subscription_command.py` 已承接命令解析 / 标题解析 / 清单回复边界，且 focused tests `17 passed, 20 deselected`
- 更早已完成主线“`search_media.py` 搜索编排层瘦身 / 模块化”已在 2026-04-19 满足 `Done when` 第 1 条；详细台账继续只看 `docs/SEARCH_MEDIA_SLIMMING_LOG.md`
- 更早已完成主线“`add_to_downloader.py` 下载编排层瘦身 / 模块化”已在 2026-04-19 满足退出条件 1；详细台账继续只看 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`
- 更早已完成主线“`import_to_library.py` 导入编排层瘦身 / 模块化”已在 2026-04-19 满足退出条件 1；详细台账继续只看 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`
- 更早已完成主线“`telegram_bot.py` 渠道层瘦身 / 模块化”已在 2026-04-19 满足退出条件 1；详细台账继续只看 `docs/TELEGRAM_BOT_SLIMMING_LOG.md`
- 更早主线“独立后台下载完成轮询剩余少量回归与验证收口”已完成；详细台账继续只看 `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 更早主线“Feishu 私聊事件解析器去重”已完成；详细台账继续只看 `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线“Feishu 长连接私有 API 风险收口”已完成；详细台账继续只看 `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线“持久化吞错收口”已完成；详细台账继续只看 `docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## 2. Risk groups

### 2.1 身份解析 / import 关联

当前风险：
- `cleanup_downloaded_source.py` 还把 `_resolve_cleanup_task_identity()`、`_find_import_correlation()`、`cleanup_by_task_ref()` / `inspect_by_task_ref()` 的入口衔接揉在同一服务文件；这一步只允许把“查询引用 -> 任务身份 -> import 关联”收成 helper，不改 cleanup guardrail、`job_event` 真相和现有中文协议。
- 这一组只允许动 identity / correlation 前半段，不顺手改 source 删除、follow-up 文案或事件落盘。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py -k "parse_cleanup_query or parse_cleanup_inspect_query or inspect_by_task_ref or resolves_chat_scoped_task_ref"`

### 2.2 inspect / execution 主路径

当前风险：
- `cleanup_downloaded_source.py` 还把 `_inspect_cleanup()`、`cleanup_by_task_ref()`、guardrail 分流和 inspect 结论组装揉在同一文件；这一步只允许按一组连贯 helper 拆开，不能顺手改删除范围、identity retention 或 reject / success 文本协议。
- 这一组继续守住“inspect 只读、execution 才删源资产；guardrail 拒绝和路径异常继续显式中文日志 + `[处理建议]`”的边界。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py -k "cleanup_by_task_ref or inspect_by_task_ref"`

### 2.3 路径校验 / source 删除 / follow-up / 事件落盘与中文日志

当前风险：
- `_validate_cleanup_paths()`、`_delete_source_asset()`、`_append_cleanup_follow_up()`、`_format_cleanup_inspect_follow_up()`、`_record_event()` 和 `_print_cleanup_*()` 仍散在同一文件；这一步只允许把“执行尾段 + 失败可观测性”继续收成 helper，不改 cleanup guardrail、删除范围或 `job_event` 真相。
- 这一组继续守住“删除失败、事件落盘失败、坏记录都必须打印显式中文日志和 fix hint，不静默吞掉”的边界。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py -k "delete_failure or source_type_unsupported or event_append_failure or missing_appended_event_result"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py -k "parse_cleanup_query or parse_cleanup_inspect_query or inspect_by_task_ref or resolves_chat_scoped_task_ref"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py -k "cleanup_by_task_ref or inspect_by_task_ref"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py -k "delete_failure or source_type_unsupported or event_append_failure or missing_appended_event_result"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.3 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 当前唯一主线已经切到 `docs/CLEANUP_SLIMMING_LOG.md`；`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md` 只继续保留完成态路径和 focused tests 入口。
