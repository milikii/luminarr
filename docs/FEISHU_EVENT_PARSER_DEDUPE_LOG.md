# Feishu event parser dedupe log (v1)

> 目的：承接当前“Feishu 私聊事件解析器去重”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 当前唯一主线：Feishu 私聊事件解析器去重
- 上一条主线“Feishu 长连接私有 API 风险收口”已在 2026-04-18 满足退出条件 1；详细台账继续只看 `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线“持久化吞错收口”已完成；详细台账继续只看 `docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## 2. Risk groups

### 2.1 webhook payload / SDK event 重复字段提取

当前风险：
- `parse_feishu_private_text_event()` 与 `parse_feishu_sdk_private_text_event()` 目前各自维护一套 `event_type / chat_type / message_type / chat_id / message_id / user_open_id / text` 提取分支。
- 这一组只允许把重复解析收口进仓库自管 helper 或统一提取路径，不改 `FeishuPrivateTextEvent` 字段形状。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_feishu_adapter.py tests/test_feishu_long_connection.py -k "parse_feishu"`

### 2.2 路由兼容 / 共享边界

当前风险：
- webhook 入口 `handle_feishu_private_text_event()` 与长连接入口 `_handle_sdk_event()` 都依赖 `FeishuPrivateTextEvent -> route_feishu_private_text_event()` 这条共享边界；去重时不能把两条链分叉成两份 runtime 入口。
- 这一组只允许改解析层，不顺手改回包、验签、shared runtime、长连接生命周期或渠道平台化。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_feishu_adapter.py tests/test_feishu_long_connection.py -k "handle_feishu_private_text_event or routes_sdk_event"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_feishu_adapter.py tests/test_feishu_long_connection.py -k "parse_feishu or handle_feishu_private_text_event or routes_sdk_event"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.2 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 只有当当前主线完成并切到下一项时，才在 `docs/NEXT_STEP.md` 和 `README.md` 切换“当前唯一主线”。
