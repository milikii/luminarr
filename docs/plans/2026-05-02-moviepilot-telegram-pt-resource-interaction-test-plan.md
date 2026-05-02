# MoviePilot-Style Telegram PT Resource Interaction Test Plan

生成时间：2026-05-02  
对应计划：`docs/plans/2026-05-02-moviepilot-telegram-pt-resource-interaction.md`

## Scope

覆盖 Telegram PT 资源卡 Phase 1：

1. 作品锁定后，返回 PT 资源卡
2. 用户通过按钮选择资源
3. 旧卡 / 重复点击 / 失败路径不会误触发下载

## Test Diagram

| Flow | Codepath | Expected UX | Test Type |
| --- | --- | --- | --- |
| 作品锁定后返回 PT 资源卡 | `search_media.py` -> Telegram PT renderer | 不是文本日志，而是 photo/text card + buttons | integration |
| 资源按钮点击 | callback -> PT card state -> add path | 点击与资源选择语义一致 | integration |
| 旧卡点击 | stale session | 明确提示卡片过期，不误选当前缓存 | integration |
| 重复点击 | second callback on consumed session | 幂等，不重复创建 pending approval | integration |
| photo fallback | `send_photo` fail | 降级 text message，但动作语义不变 | unit / integration |
| callback token budget | PT card keyboard | callback data < 64 bytes | unit |
| approval handoff | resource button -> existing pending approval | 进入现有待确认路径，不改 approval 真相 | integration |

## Required Tests

- `tests/test_telegram_pt_resource_cards.py`
  - card formatter
  - callback token grammar
  - mobile truncation rules
- `tests/test_telegram_runtime_adapter.py`
  - callback edit / stale / consumed state
- `tests/test_private_chat_selection_runtime.py`
  - resource button path and chat cache independence
- `tests/test_search_media.py`
  - candidate-first remains intact
  - PT resource card trigger after media lock

## Manual Smoke

1. Telegram 发送 `超人`
2. 选择作品候选
3. 看到 PT 资源卡，而不是长文本日志
4. 点一个资源按钮
5. 原消息按钮移除或失效
6. 收到现有待确认下载消息
7. 再回点旧卡，必须提示已过期或已处理

## Gates

- `make quality`
- `make verify-mainline`
- `make verify-stage1-telegram-delivery`
- focused PT card suite
