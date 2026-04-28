# Message Interaction And Card Delivery Test Plan

生成时间：2026-04-29  
对应计划：`docs/plans/2026-04-29-message-interaction-and-card-delivery.md`

## 1. Scope

覆盖消息交付层重构后最容易回归的三类能力：

1. 文本卡片排版是否稳定
2. Telegram 按钮是否正确发出并能回到 shared runtime
3. Feishu card / action 是否与文本 fallback 保持同一业务语义

## 2. Test Diagram

| Flow | Codepath | Expected UX | Test Type |
| --- | --- | --- | --- |
| 搜索结果文本渲染 | `app/services/search_reply_formatter.py` -> `app/runtime/delivery.py` | 标题、候选、动作区顺序稳定 | unit |
| 下载待确认文本渲染 | `app/services/add_to_downloader.py` -> `app/runtime/delivery.py` | 待确认标题、任务信息、确认/取消动作稳定 | unit |
| 状态文本渲染 | `app/services/get_download_status.py` -> `app/runtime/delivery.py` | 状态摘要、后续、刷新动作稳定 | unit |
| Telegram 发送搜索结果 | `app/bot/telegram_runtime_adapter.py` + telegram delivery helper | 发送文本时同时带 inline buttons | unit |
| Telegram 按钮点击回流 | `CallbackQueryHandler` -> `handle_telegram_callback_query()` -> shared runtime | 点击与手输命令语义一致 | unit / integration |
| Telegram 过期按钮 | callback -> confirm / cancel / select stale case | 明确提示过期，不 silently fail | integration |
| Telegram 多选项选择 | search / BT follow-up choice | 选项过多时分页或缩略策略稳定 | integration |
| Feishu 文本 fallback | `app/bot/feishu_adapter.py` + text renderer | 未开 card 时继续可读 | unit |
| Feishu card payload | `app/clients/feishu.py` card builder | header / section / action schema 正确 | unit |
| Feishu action callback | callback payload -> shared runtime query | 动作点击与文本命令一致 | unit / integration |
| WeCom 文本 fallback | `app/bot/wecom_adapter.py` | 继续返回规整文本 | unit |
| personal WeChat 文本 fallback | `app/bot/personal_wechat_text.py` | 继续返回规整文本 | unit |
| 错误 / unavailable 态 | capability missing / state unavailable | 标题、原因、建议、下一步齐全 | unit |

## 3. Required New Tests

### 3.1 Delivery model

- `tests/test_delivery_renderers.py`
  - 增加搜索 / 审批 / 状态 / 错误四类 golden-style 断言
  - 校验四渠道动作区是否稳定

### 3.2 Telegram

- 新增 `tests/test_telegram_delivery_runtime.py`
  - inline keyboard payload 生成
  - `callback_data` 编码与长度控制
  - 文本 fallback 同步存在

- 扩充 `tests/test_telegram_runtime_adapter.py`
  - callback -> query round-trip
  - 重复点击 / callback 去重
  - 过期 / stale 按钮提示

### 3.3 Feishu

- 新增 `tests/test_feishu_delivery_cards.py`
  - card schema
  - action payload
  - 文本 fallback

- 扩充 `tests/test_feishu_adapter.py`
  - action callback 回译为 shared query
  - card unavailable 时退回文本

### 3.4 Shared flow regressions

- 扩充：
  - `tests/test_private_chat_search_runtime.py`
  - `tests/test_private_chat_confirm_runtime.py`
  - `tests/test_private_chat_import_runtime.py`
  - `tests/test_private_chat_bt_*_runtime.py`

重点验证：

- 按钮触发与手输命令返回同一结果
- query 语义不分叉
- unavailable / pending / expired 文本不丢

## 4. Manual Smoke

### Telegram

1. 发 `我想看 Dune 2021`
2. 看到候选列表与按钮
3. 点“选择 1”
4. 看到下载待确认卡片与“确认 / 取消”按钮
5. 点确认后检查任务已创建

### Feishu

1. 发同样搜索词
2. 若 card 开启，检查卡片内容与动作区
3. 若 card 未开启，检查文本 fallback 仍清楚
4. 任一动作点击后应与文本命令一致

### WeCom / personal WeChat

1. 搜索、状态、确认消息仍能读懂
2. 命令提示可直接复制
3. 不出现过长首屏滚动

## 5. Gates

- `make quality`
- `make verify-mainline`
- 新增一个 focused target，示例：`make verify-message-delivery`
- 四渠道至少保住当前文本主链不回退

## 6. Failure Criteria

出现以下任一情况，视为不可发布：

- Telegram 点击按钮与手输命令结果不一致
- Feishu card action 与文本 fallback 结果不一致
- 文本排版把关键命令藏进长段落
- 选择项过多时无截断 / 分页策略
- 渠道之间字段含义不一致
