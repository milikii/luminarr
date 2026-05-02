<!-- /autoplan restore point: /tmp/main-autoplan-restore-20260502-203514.md -->

# MoviePilot-Style Telegram PT Resource Interaction Plan

生成时间：2026-05-02  
状态：draft for `/autoplan` review

## 1. Goal

在 **不改变现有主业务顺序** 的前提下，把 Luminarr 的 Telegram PT 资源交互升级到接近 `MoviePilot` 的体验：

1. 先锁定作品候选
2. 再展示 PT 资源候选
3. 再进入下载确认

本计划只针对 **Telegram 的 PT 资源交互**，重点解决“资源列表像日志、交互像命令行”的问题。

## 2. Locked Product Rules

这些是已经锁死、review 不应推翻的前提：

- **候选优先**：必须先锁定作品候选，不能先搜资源再反推作品。
- **Telegram first**：首个 richer interaction 只做 Telegram。
- **不改业务真相边界**：不改 approval、jobs、lease、downloader dispatch 真相。
- **不扩到成人 BT**：本计划只覆盖普通影视 PT 资源交互，不顺手改 adult BT。
- **不扩到其他渠道**：Feishu / personal WeChat / WeCom 不在本轮。
- **非目标：行为克隆**：目标是借鉴 MoviePilot 的交互原则，不追求消息结构、流程顺序、状态机与 MoviePilot 完全一致。

## 3. Current Local Reality

### 3.1 What already exists

- `app/services/search_reply_formatter.py`
  现在已经会生成：
  - 作品候选确认文本
  - PT 搜索结果文本
  - `DeliveryItem` / `DeliveryAction` 结构
- `app/runtime/delivery.py`
  当前 delivery model 还是“header + sections + actions + footer”的文本中心模型。
- `app/bot/telegram_delivery_runtime.py`
  已经支持：
  - `send_message(parse_mode="HTML")`
  - 从动作行自动组装 `InlineKeyboardMarkup`
  - `send_photo(..., reply_markup=...)`
- `app/bot/telegram_update_runtime.py`
  已经支持：
  - 候选海报卡片
  - per-candidate button
  - placeholder poster fallback
- `app/bot/private_chat_selection_runtime.py`
  仍然是：
  - 数字选择作品候选 -> `search_resources_for_selected_media()`
  - 资源选择 -> `add_by_selection()`

### 3.2 Current PT interaction problem

- PT 资源列表仍然是文本段落，不像卡片。
- `开始下载：发送 select 1` 仍是主交互。
- 资源元信息（画质、大小、站点）已经有，但视觉层级太弱。
- Telegram 传输层已经具备按钮能力，但 PT 资源交互还没有真正“消息即界面”。

## 4. MoviePilot Experience We Intend To Emulate

从公开文档和生态用法里，抽出的不是“抄代码”，而是这些稳定模式：

### 4.1 Media-first notification pattern

- 一条消息尽量承载完整事件
- 图片 / 海报优先
- 标题、正文、链接、动作按钮聚合在同一个消息单元里

参考：
- MoviePilot Telegram notification docs: https://opendeep.wiki/jxxghp/MoviePilot/telegram-notification

### 4.2 Button-first interaction pattern

- 用户优先点按钮，不优先手打命令
- 回调后允许更新原消息或移除按钮，避免重复点击
- callback payload 是短 token，不把长文本塞进按钮

参考：
- MoviePilot plugin button interaction docs: https://github.com/jxxghp/MoviePilot-Plugins/blob/main/docs/API/PluginBase.md

### 4.3 Compact resource decision pattern

- 资源选择不是长日志，而是“可扫描的摘要 + 少量关键指标 + 一键动作”
- 用户决策最依赖：
  - 资源名
  - 画质 / source type
  - 大小
  - 做种数
  - 来源站点

## 5. Proposed UX

## 5.1 Flow A — Media candidate confirmation

保持现有 candidate-first 主线，不作为本计划主改造点，只要求与后续 PT 资源卡片风格统一。

结果：
- 用户先锁定作品
- 锁定后才允许进入 PT 资源卡片

## 5.2 Flow B — PT resource picker card

触发条件：
- 作品候选已锁定
- `search_resources_for_selected_media()` 拿到 PT 候选

Telegram 目标形态：

1. **优先单消息**
   - 若有作品海报：`send_photo(photo=poster, caption=html, reply_markup=keyboard)`
   - 若无海报：`send_message(text=html, reply_markup=keyboard)`

2. **卡片内容**
   - 主标题：`<b>Superman (2025)</b>`
   - 副信息：年份 / 类型 / 简短简介
   - 分隔线后展示 top 3~5 PT 资源
   - 每条资源显示：
     - 资源标题
     - `quality shorthand`
     - `size`
     - `seeders`
     - `indexer`

3. **按钮布局**
   - 每个资源一个选择按钮
   - 两列排布，按钮文字尽量短：
     - `1 · 4K WEB 45G`
     - `2 · 1080p BD 28G`
   - 辅助按钮：
     - `换关键词`
     - `取消`

4. **点击后反馈**
   - 资源选择按钮点击后，原消息按钮应移除或替换成 disabled state
   - 防止重复投递

5. **Phase 1 mobile contract**
   - 有海报时每页只展示 `3` 条资源
   - 无海报时最多展示 `5` 条资源
   - 每条资源正文最多 `2` 行
   - 按钮文案目标上限 `18` 个可见字符
   - caption 超过 Telegram 安全预算时，优先截断简介，不截断资源核心字段

## 5.3 Flow C — Download approval handoff

本轮不是完整审批重构。

Phase 1 只要求：

- 资源按钮点击 -> 进入现有 pending approval 路径
- 不改变当前 approval 真相模型
- approval 卡片沿用现有按钮化路径，不在本轮重做状态协议或布局体系

## 6. Proposed Technical Shape

### 6.1 Preserve current truth boundaries

- 作品选择仍然走 `search_resources_for_selected_media()`
- 资源选择仍然走现有 selection / add path
- 不把按钮协议直接扩成新的后台业务协议

### 6.2 Telegram-specific rendering layer

优先在 Telegram 层新增一种明确的 **PT resource card rendering path**，而不是继续让纯文本 `DeliveryItem` 承担全部 richer UI。

建议方向：

- `search_reply_formatter.py`
  - 继续产出结构化 PT 资源候选数据
  - 不在这里写死 Telegram 视觉文案
- `telegram_reply_formatter.py`
  - 增加 PT resource card 的 HTML 组装
- `telegram_update_runtime.py`
  - 增加 `_is_pt_resource_card_reply()` / `_send_pt_resource_card()` 风格的专门 dispatcher
  - 统一处理：
    - `send_photo + caption + keyboard`
    - callback -> select / retry / cancel

### 6.3 PT card state contract

Phase 1 必须新增 Telegram 专用的 PT card session / snapshot 状态层，不能继续复用裸数字 callback 和 chat 级 `candidate_mapping`。

最低字段：

- `session_token`
- `chat_id`
- `message_id`
- `resource_snapshot_id`
- `resource_items`
- `selected_index`
- `consumed_at`
- `expires_at`
- `status` (`active / selected / cancelled / expired`)

约束：

- callback data 必须是短 token，而不是原始标题/查询
- 同一张卡首次消费后，必须 edit 原消息移除或替换按钮
- 新搜索覆盖 chat 级候选缓存时，旧 PT 资源卡 callback 仍必须安全失效，而不是误触发另一条 `selection_index`

### 6.4 Callback data strategy

不要把长 query 或完整资源标题塞进 callback data。

统一使用短 token：
- `ptr:<session>:s:<slot>`
- `ptr:<session>:r`
- `ptr:<session>:x`

真正的数据从 Telegram 专用 PT card session / snapshot 读取，不从 chat 级普通候选缓存反推。

### 6.5 Poster strategy

- 优先用已锁定作品的海报
- 不按每个 PT 资源单独找图
- 没图就优雅降级到 text message，不暴露“海报：暂未接入图片”

## 7. Scope Proposal

### In scope

- Telegram PT 资源选择卡片
- Telegram 专用 PT card session / snapshot 状态层
- Telegram PT 资源按钮交互
- Telegram PT 资源 `重试 / 取消`
- 原消息 edit / 按钮失效
- 与现有下载待确认 handoff 的最低一致性交互
- 相关测试与 focused verification

### Out of scope

- PT 资源分页（Phase 2 再议；Phase 1 不做）
- 下载确认卡重设计
- 改 Feishu / WeCom / personal WeChat
- 改 adult BT
- 改 downloader routing / approval persistence / import flow
- 做 Web UI
- 重写整个 `DeliveryItem` 体系

## 8. Acceptance Criteria

- 用户锁定作品后，Telegram 返回 **PT 资源卡片**，而不是纯文本日志块
- 用户优先通过按钮选择 PT 资源，而不是手打 `select 1`
- 资源卡片能稳定显示 top 资源的关键决策信息：标题、画质、大小、做种、站点
- 资源按钮点击后，不会重复触发同一条资源选择
- 旧资源卡或旧作品卡再次点击时，会安全失效，不会误命中新搜索的 `selection_index`
- callback token 长度始终 < `64 bytes`
- 现有 candidate-first 主线不回退
- 现有非 Telegram 渠道不被顺手改坏

## 9. User State Matrix

| State | User Sees | System Requirement |
| --- | --- | --- |
| 作品已锁定，返回 PT 资源 | 海报 + 资源摘要 + 选择按钮 | 生成 active PT card session |
| 资源选择成功 | 原卡按钮失效 / 被移除 | session 标记为 selected |
| 资源卡重复点击 | 明确提示已处理或已过期 | 不重复创建待确认 |
| 用户点击旧卡 | 明确提示卡片已过期 | 不读取新的 chat 级 selection 映射 |
| 无 PT 资源 | 明确无资源状态 + 重试入口 | 不创建空 session |
| 状态写入失败 | 明确 service unavailable / retry 提示 | 不留下半有效按钮 |
| 用户取消 | 原卡失效 + 结束提示 | session 标记为 cancelled |

## 10. Test Plan

- Unit
  - PT resource card formatter
  - quality shorthand mapping
  - callback token parsing
  - PT card session token/state transitions
- Integration
  - Telegram resource card send path
  - callback -> resource selection round-trip
  - button disable / reply markup removal
  - stale card invalidation
  - duplicate click idempotency
- Regression
  - media candidate confirmation still precedes PT resource selection
  - existing `传奇` / `丧尸` / `Dune 2021` 样例不回退
  - `make verify-stage1-telegram-delivery`

## 11. Open Design Questions

- `DeliveryItem` 是否只做轻扩展，还是保持 Telegram richer card 走专门路径

## GSTACK REVIEW REPORT

### Phase 1 — CEO Review

#### Premise Challenge

- Premise 1: “严格按照 MoviePilot” 应理解为借鉴交互原则，不应理解为流程与状态机克隆。
- Premise 2: candidate-first 主线是本项目锁死前提，不能为了更像 MoviePilot 改成资源优先。
- Premise 3: PT 资源交互要变得像产品，而不是像日志，但不能把同一轮 scope 扩成 approval / status / cross-channel 全栈重做。

#### What Already Exists

| Sub-problem | Existing Code |
| --- | --- |
| 作品锁定后再搜资源 | `app/services/search_media.py` + `app/bot/private_chat_selection_runtime.py` |
| Telegram HTML / 按钮 / 图片发送 | `app/bot/telegram_delivery_runtime.py` |
| Telegram 候选海报卡经验 | `app/bot/telegram_update_runtime.py` |
| 现有下载确认按钮 | 现有 approval delivery + Telegram inline keyboard path |

#### Dream State

```text
CURRENT
候选优先是对的 -> PT 资源像日志 -> 主要靠手打 select 1

THIS PLAN
候选优先不变 -> PT 资源卡片化 -> 按钮优先选择 -> 进入现有待确认路径

12-MONTH IDEAL
Telegram 资源交互完整产品化 -> 状态/审批/失效语义统一 -> 其他渠道有计划地跟进
```

#### Implementation Alternatives

| Approach | Effort | Pros | Cons | Verdict |
| --- | --- | --- | --- | --- |
| A. Telegram 专用 PT card path + session state | M | 最贴近 MoviePilot 体验；最不污染现有文本模型 | 需要新增状态层 | 推荐 |
| B. 强行扩 `DeliveryItem` 承担分页和状态 | M-L | 理论上更通用 | 会把文本模型拖进 Telegram 状态机 | 拒绝 |
| C. 继续文本，只把动作提示变好看 | S | 风险最低 | 不会显著改善交互体验 | 拒绝 |

#### Scope Decisions

- Phase 1 纳入：PT 资源卡片、Telegram 专用 state、短 callback token、旧卡失效、按钮移除、focused tests。
- Phase 1 移出：分页、approval 卡重设计、跨渠道统一、adult BT。

#### Error & Rescue Registry

| Condition | User Impact | Rescue |
| --- | --- | --- |
| PT card state 写入失败 | 按钮不可安全使用 | 退回文本错误提示，不发半有效按钮 |
| 旧卡点击 | 误命中当前缓存 | 明确提示“卡片已过期” |
| 资源选择重复点击 | 重复建待确认 | session 首次消费后立即失效 |
| send_photo 失败 | 看不到卡片 | 降级 send_message + 同一组按钮 |

#### Failure Modes Registry

| Failure Mode | Severity | Mitigation |
| --- | --- | --- |
| 旧按钮命中新搜索的 `selection_index` | Critical | 禁止裸数字 callback；session token 化 |
| 分页依赖 chat 级切片缓存 | Critical | Phase 1 去掉分页 |
| 把 approval 一起重做导致 blast radius 扩大 | High | approval 只沿用现有路径 |

#### CEO Dual Voices — Consensus

| Dimension | Main Review | Independent Review | Consensus |
| --- | --- | --- | --- |
| Right problem to solve? | PT 资源日志感过强，需要产品化 | 同意 | CONFIRMED |
| Clone MoviePilot literally? | 不应克隆，应 selective adaptation | 同意 | CONFIRMED |
| Scope should include pagination? | Phase 1 不应包含 | 担忧很高 | CONFIRMED |
| Scope should include approval redesign? | 不应包含 | 不应包含 | CONFIRMED |

#### CEO Completion Summary

- Verdict: `SELECTIVE_EXPANSION`
- Recommendation: 做“Telegram PT picker + state contract”，不做 MoviePilot parity

### Phase 2 — Design Review

#### Design Scorecard

| Dimension | Score / 10 | Notes |
| --- | --- | --- |
| Information hierarchy | 9 | 标题 -> 副信息 -> top 资源 -> 动作 很清楚 |
| Scanability | 8 | quality / size / seeders / site 是正确摘要 |
| Mobile ergonomics | 7 | 已补 3/5 条密度规则，但还需实现验证 |
| Interaction clarity | 8 | button-first 正确，旧卡失效已显式化 |
| State completeness | 7 | 已补状态矩阵，分页 deferred 减少歧义 |
| Specificity | 8 | 现在足够指导实现，不再停留在“像 MoviePilot” |
| Consistency with current product | 9 | 保留 candidate-first 与现有 approval handoff |

#### Design Findings

- 必须避免“单消息塞满全部信息”导致移动端更难扫；因此 Phase 1 固定 3 条带海报资源。
- “像 MoviePilot” 的重点是 poster-first 和 button-first，不是无限追求单条 caption 的内容密度。

#### Design Litmus

| Question | Main Review | Independent Review | Consensus |
| --- | --- | --- | --- |
| Does it feel like a product, not a log? | Yes | Yes | CONFIRMED |
| Are mobile constraints explicit? | Now mostly yes | Needed and now added | CONFIRMED |
| Are interaction states complete? | Mostly yes for Phase 1 | Needed more explicit matrix | CONFIRMED |

### Phase 3 — Engineering Review

#### Architecture ASCII

```text
search_resources_for_selected_media()
        |
        v
  PT resource snapshot builder
        |
        +--> Telegram PT card state store (session_token, items, status, expiry)
        |
        v
telegram renderer (photo/text + html + keyboard)
        |
        v
callback_query handler
        |
        +--> validate session / status / expiry
        +--> select item OR retry OR cancel
        +--> edit original message reply_markup
        |
        v
existing pending approval path
```

#### What Already Exists

- 作品确认后搜资源：已存在
- Telegram media/button transport：已存在
- PT resource state model：不存在
- safe callback invalidation：不存在

#### Engineering Findings

- 不能复用 chat 级 `candidate_mapping` 做 PT 资源按钮状态。
- 不能在 Phase 1 做分页，否则没有完整 snapshot store 就会错页。
- 资源卡渲染不应继续靠纯文本正则反解，Phase 1 就该引入 Telegram 专用结构化 payload。

#### Test Diagram

| Flow | Codepath | Required Test |
| --- | --- | --- |
| 作品锁定 -> PT 资源卡 | `search_media.py` -> Telegram renderer | integration |
| 资源按钮点击 | callback -> PT state validation -> select | integration |
| 旧卡失效 | callback on stale session | integration |
| 重复点击幂等 | callback twice with different ids | integration |
| photo send fallback | send_photo fail -> send_message | unit/integration |

#### Failure Modes Registry

| Failure Mode | Severity | Fix |
| --- | --- | --- |
| 旧作品卡点击变成资源选择 | Critical | 独立 session token |
| 资源卡重复点击重复建任务 | Critical | consumed flag + edit message |
| callback token 过长 | High | short token grammar |
| caption 过长 | Medium | hard truncation budget |

#### Eng Completion Summary

- Recommended Phase 1 architecture: `Telegram-specific PT card renderer + Telegram PT card state store`
- Rejected architecture: `chat-level cache reuse`, `generic DeliveryItem pagination`

### Cross-Phase Themes

- Theme: **Selective adaptation, not clone** — product、design、engineering 三个视角都确认这不是 MoviePilot parity 项目。
- Theme: **State contract before pretty UI** — 如果先做漂亮按钮而不补 state contract，旧卡误触发会直接破坏正确性。

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|
| 1 | CEO | 选择性适配 MoviePilot，而不是克隆流程 | User Challenge | Pragmatic | 本地 candidate-first 真相不可推翻，克隆会直接冲突 | full parity clone |
| 2 | CEO | Phase 1 去掉分页 | Taste | Explicit over clever | 当前没有可靠 snapshot store，先去掉分页能显著降风险 | page 2 in v1 |
| 3 | Eng | 新增 Telegram 专用 PT card state 层 | Mechanical | Explicit over clever | 现有 chat 级缓存无法保证旧卡安全失效 | reusing candidate_mapping |
| 4 | Design | 固定 mobile contract：有海报 3 条，无海报 5 条 | Taste | Pragmatic | 先锁定移动端信息密度，减少 caption 爆炸 | undefined 3~5 |
| 5 | Eng | Phase 1 不重做 approval 卡协议 | Mechanical | DRY | 现有 approval button path 已存在，重做只扩大 blast radius | approval redesign in same phase |
