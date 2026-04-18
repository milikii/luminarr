# Feishu long connection risk log (v1)

> 目的：承接当前“Feishu 长连接私有 API 风险收口”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 上一条主线：Feishu 长连接私有 API 风险收口（已在 2026-04-18 满足退出条件 1：`app/bot/feishu_long_connection.py` 不再直接引用 `lark_ws_client_module.loop`、`_disconnect`、`_auto_reconnect`、`_cache`，且 `tests/test_feishu_long_connection.py` 全绿）
- 更早主线“持久化吞错收口”已在 2026-04-18 冷启动审计中满足退出条件 3；详细台账继续只看 `docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## 2. Risk groups

### 2.1 启动 / 线程事件循环绑定

当前状态：
- 2026-04-18 已完成：线程先 `set_event_loop(thread_loop)`，再在当前线程重载 `lark_oapi.ws.client` 模块并实例化 `Client`，不再直接写 `lark_ws_client_module.loop`。
- shared runtime、回包协议和 Feishu webhook 入站保持不变；对应回归继续看下面 focused tests。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_feishu_long_connection.py -k "routes_sdk_event or does_not_log_start_failure or logs_unexpected_loop_stop_failure or suppresses_expected_loop_stop_error"`

### 2.2 停机 / 断链

当前状态：
- 2026-04-18 已先收口一轮：`shutdown()` 改为只请求长连接线程事件循环停止并 `join`，不再直接触碰 `_auto_reconnect`、`_disconnect()`、`_cache`。
- 预期关闭仍不报错；如果请求线程 loop 停止时抛出非预期异常，仍打印显式中文日志和 `[处理建议]`。
- 这一组剩余风险只剩 SDK 内部如何响应 loop stop，不再由仓库代码直接摸它的私有属性。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_feishu_long_connection.py -k "shutdown"`

### 2.3 事件桥接 / 生命周期接线

当前风险：
- 事件桥接依赖主线程 loop、长连接线程 loop 和 `telegram_bot.py` 的启停包装协同；收口时不能把 Feishu 事件从 shared runtime 分叉出去。
- 这一组只允许改长连接服务和其生命周期接线，不顺手做 Feishu 事件解析去重或渠道平台化。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_feishu_long_connection.py -k "routes_sdk_event or parse_feishu_sdk_private_text_event"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_feishu_long_connection.py`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.3 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 只有当当前主线完成并切到下一项时，才在 `docs/NEXT_STEP.md` 和 `README.md` 切换“当前唯一主线”。
