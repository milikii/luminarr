# Private chat runtime slimming log (v1)

> 目的：承接当前“`private_chat_runtime.py` shared runtime 编排层瘦身 / 模块化”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 当前主线状态：`private_chat_runtime.py` shared runtime 编排层瘦身 / 模块化已在 2026-04-19 满足 `Done when` 第 2 条：入站 trace 和回包 trace 已抽到 `_log_private_chat_inbound()` / `_wrap_reply_with_trace()` helper，focused tests `34 passed, 17 deselected`
- 上一条已完成主线“`cleanup_downloaded_source.py` cleanup 编排层瘦身 / 模块化”已在 2026-04-19 满足 `Done when` 第 1 条：`app/services/cleanup_correlation_lookup.py` 已承接“查询引用 -> 任务身份 -> import 关联”边界，且 focused tests `18 passed, 28 deselected`
- 更早已完成主线“`manage_bt_subscription.py` 订阅编排层瘦身 / 模块化”已在 2026-04-19 满足 `Done when` 第 1 条
- 下一次施工按 `docs/NEXT_STEP.md` 的 `After this step` 第 1 项切到 `app/main.py` 启动装配 / 下载器路由 helper 瘦身 / 模块化
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## 2. Risk groups

### 2.1 frustration reset / pending state gate

当前风险：
- `private_chat_runtime.py` 还把 frustration reset、clarification / candidate 清理、BT pending state gate、confirm / cancel 前置检查揉在同一入口函数里；这一步只允许把“先判有没有未完成状态，再决定继续执行还是停路回复”收成 helper。
- 这一组只允许动 shared runtime 前置闸门，不顺手改四渠道协议、approval、`jobs` 或 SQLite 真相。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py -k "pending_job_lookup_failure or pending_downloader_cancel_state_unavailable or clarification_lookup_failure or bt_processing_path or bt_classification or bt_tmdb or raw_bt_destination"`

### 2.2 命令分发 / cleanup-search-bt 路由

当前风险：
- `private_chat_runtime.py` 还把普通搜索、BT 追问、cleanup inspect / execution、登录入口和数字确认分发堆在同一个 dispatch 主路径；这一步只允许把“文本 -> 动作分支 -> service 调用”收成 helper。
- 这一组继续守住“同一条自然语言协议仍落到同一 shared runtime；四个渠道只是透传 text/chat_id/user_id”的边界。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py -k "routes_search_without_telegram_update or routes_bt_prompt_without_telegram_update or routes_cleanup or routes_bare_cleanup or personal_wechat_login"`

### 2.3 shared reply 包装 / trace / service-not-ready 回复

已完成闭环：
- shared runtime 已把入站 trace 和渠道无关回包 trace 抽到 `_log_private_chat_inbound()` / `_wrap_reply_with_trace()` helper；业务分流、最终回复文本和日志协议保持不变。
- 这一组继续守住“trace 只是补充观测，不替代中文失败日志”的边界；`SERVICE_NOT_READY_TEXT` 回复语义未改。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py -k "writes_trace_log or replies_service_not_ready or stops_on_confirm_job_lookup_failure_even_with_services or stops_on_pending_job_lookup_failure_even_with_services"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py -k "pending_job_lookup_failure or pending_downloader_cancel_state_unavailable or clarification_lookup_failure or bt_processing_path or bt_classification or bt_tmdb or raw_bt_destination"`
- `.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py -k "routes_search_without_telegram_update or routes_bt_prompt_without_telegram_update or routes_cleanup or routes_bare_cleanup or personal_wechat_login"`
- `.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py -k "writes_trace_log or replies_service_not_ready or stops_on_confirm_job_lookup_failure_even_with_services or stops_on_pending_job_lookup_failure_even_with_services"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.3 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 该主线已在 2026-04-19 完成；后续只保留完成态路径和 focused tests，下一条主线按 `docs/NEXT_STEP.md` 的 `After this step` 第 1 项推进。
