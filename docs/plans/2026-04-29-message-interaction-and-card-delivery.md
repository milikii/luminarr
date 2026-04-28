<!-- /autoplan restore point: /tmp/luminarr-message-interaction-autoplan-restore-20260429-013407.md -->
# Message Interaction And Card Delivery Plan

生成时间：2026-04-29  
分支：`main`  
状态：DRAFT  
来源：当前仓库代码、`docs/assets/luminarr_visual_specs.md`、用户新增需求

## 1. Problem

当前仓库已经有跨渠道 `DeliveryItem` 文本渲染骨架，也有 4 张消息卡片效果图，但真正落到运行时的交互仍然偏“长文本 + 手动输入命令”。

这带来 3 个实际问题：

1. 搜索结果、待确认下载、待确认导入、状态查询、BT follow-up、cleanup 等关键消息虽然能用，但层级还不够稳定，用户要自己读懂结构。
2. Telegram 虽然已经有 `callback_query` 路由能力，但当前没有真正把按钮发出去，导致“能点”和“只能手输”之间断层明显。
3. Feishu、WeCom、personal WeChat 目前都走纯文本收发，缺少一份明确的渠道能力边界和渐进增强路线，容易让视觉稿、代码真相和用户预期分裂。

## 2. Goal

把“消息排版、卡片化、命令引导、按钮交互”做成一套可复用的消息交付层，让用户在四个私聊渠道里都能获得：

- 一眼能读懂的层级
- 明确的下一步操作
- 在支持的平台上优先点击，不强迫背命令
- 在不支持的平台上继续用文本命令，但格式足够整齐、短促、可抄

这里追求的是“同一业务语义”，不是“四个渠道长得一模一样”。按钮、卡片、纯文本可以不同，但用户在任何渠道里都必须知道自己正在做同一件事。

## 3. User Value

- 搜索和选片时，用户更快看懂候选差异，减少选错片。
- 下载确认、导入确认、cleanup、BT 路径选择这类高风险动作，用户不需要在大段文字里找命令。
- Telegram 用户可以先享受按钮式确认和选择，Feishu 后续可进入卡片化交互，不把所有渠道一刀切成最低公分母。
- WeCom / personal WeChat 即使保持文本，也能得到更规整、更像卡片的消息版式。

## 4. Current Truth

### 4.1 已经存在的东西

- `app/runtime/delivery.py` 已有 `DeliveryItem / DeliveryHeader / DeliverySection / DeliveryAction`。
- `app/services/search_reply_formatter.py` 已经在搜索结果里构造 `DeliveryItem`。
- `app/services/add_to_downloader.py` 已经在下载待确认里构造 `DeliveryItem`。
- `app/services/get_download_status.py` 已经在状态查询里构造 `DeliveryItem`。
- `tests/test_delivery_renderers.py` 已经覆盖 Telegram / Feishu / personal WeChat / WeCom 的文本渲染。
- `docs/assets/luminarr-card-telegram.png`、`docs/assets/luminarr-card-feishu.png` 等视觉稿已经表达“希望更像卡片”的方向。

### 4.2 当前缺口

- Telegram 发送文本仍走 `application.bot.send_message(..., text=text)`，没有 `reply_markup`。
- Telegram `callback_query` 处理已经存在，但当前没有把 `DeliveryAction` 变成真正的 inline button。
- Feishu 发送当前只调用 `FeishuClient.send_private_text()`，没有消息卡片 payload。
- WeCom 当前回包仍是加密 XML 文本消息。
- personal WeChat 当前只发文本。
- 只有少数主链消息使用 `DeliveryItem`；很多 follow-up 仍是手工拼接字符串。

## 5. Capability Matrix

| 渠道 | 平台能力 | 当前仓库能力 | 本计划目标 |
| --- | --- | --- | --- |
| Telegram | 支持消息按钮与 callback | 已能接 callback；未发按钮 | Phase 1 做成首个富交互渠道 |
| Feishu | 平台支持卡片消息 / 交互动作 | 当前只收发文本 | Phase 2 做卡片化与动作回调 |
| WeCom | 当前仓库按纯文本 webhook 回包 | 纯文本 | 继续文本优先，强化排版 |
| personal WeChat | 当前仓库按纯文本轮询收发 | 纯文本 | 继续文本优先，强化排版 |

## 6. Priority Flows

本计划只覆盖真正高频、容易误操作、最值得美化的消息流：

1. 搜索结果与正确影片选择
2. 下载待确认
3. 导入待确认
4. 下载状态 / 刷新状态
5. BT processing-path 选择
6. BT 媒体分类选择
7. BT TMDB 候选选择
8. raw BT 下载目录选择
9. cleanup inspect / cleanup 执行前后的提示
10. watchlist / btsub / 命令帮助 / 常见设置命令的格式统一

## 7. UX Direction

### 7.1 全渠道统一的视觉语言

- 每条关键消息都拆成：标题、摘要、主体信息、下一步。
- 关键标识统一显式化：`待确认`、`已完成`、`不可用`、`风险操作`。
- 让命令从“埋在正文里”改成固定的动作区。
- 对文本渠道，命令提示要可直接复制，不使用过长自然语言。
- 不以“更像卡片”为目标，而以“首屏更快读懂、下一步更少犹豫”为目标。

### 7.2 渠道差异化策略

- Telegram：优先按钮，其次保留文本命令 fallback。
- Feishu：优先卡片布局和动作区，保留文本 fallback。
- WeCom / personal WeChat：文本卡片化，不承诺按钮。

## 8. Design Proposal

### Approach A: Shared Intent + Per-Channel Renderer

- 继续以 `DeliveryItem` 为 shared intent。
- 把 `DeliveryAction` 升级成既能渲染“文本提示”，又能渲染“真实按钮 / 卡片动作”的统一动作模型。
- Telegram renderer 负责把动作转成 inline keyboard。
- Feishu renderer 负责把同一份 intent 转成 card payload。
- WeCom / personal WeChat 继续渲染为文本。

优点：
- 复用已有 delivery 骨架，风险最低。
- 频道差异只在 renderer，不把业务逻辑拆碎。
- 允许逐渠道渐进增强。

缺点：
- 需要重新定义 `DeliveryAction` 的字段与稳定动作 ID。
- 会触碰若干现有文本 formatter。

### Approach B: Telegram / Feishu 各自单独做

- Telegram 单做 inline keyboard。
- Feishu 单做 card builder。
- 其他渠道不改 shared delivery model。

优点：
- 起步快，能先看到 Telegram 效果。

缺点：
- 逻辑容易分叉。
- 同一条审批消息会在两个渠道里分别维护。

### Approach C: 只做文本美化，不做真正按钮

- 所有渠道继续发文本。
- 统一标题、分节、动作提示格式。

优点：
- 最稳。
- 改动小。

缺点：
- Telegram 和 Feishu 的平台能力被浪费。
- 用户仍要手动输入确认命令。

**推荐：Approach A。**

## 9. Interaction Model

新增统一动作语义，而不是让 UI 层直接拼业务命令：

- `select_candidate`
- `confirm_download`
- `cancel_download`
- `confirm_import`
- `cancel_import`
- `refresh_status`
- `choose_bt_path`
- `choose_bt_media_kind`
- `choose_tmdb_candidate`
- `choose_raw_bt_destination`
- `run_cleanup_inspect`
- `run_cleanup`

对共享 runtime 的约束：

- 所有按钮最终仍然落回现有私聊 query 语义，避免再造第二套业务入口。
- Telegram `callback_data` 可以直接携带短 query，或携带动作 ID + payload 后在 adapter 里翻译回 query。
- Feishu card action 也必须回译到同一套 shared query / action dispatcher。
- 按钮文案、文本命令、callback 动作、过期行为必须是一一对应的；任何一个渠道都不能出现“点按钮”和“发命令”结果不同。

## 10. Message Layout Spec

### 10.1 搜索结果

- 标题区：搜索词、候选数量、结果状态
- 电影信息区：片名、年份、别名、可选海报
- 候选区：序号、标题、年份、画质、大小、站点
- 动作区：
  - Telegram：候选按钮 + “换关键词”
  - Feishu：候选动作按钮 / 下拉
  - 其他渠道：`发送 select 1`

### 10.2 下载 / 导入确认

- 标题区明确写 `待确认`
- 主体区固定展示任务标识、片名、来源、过期时间
- 动作区固定只有“确认 / 取消”
- 所有危险动作都保留文本命令 fallback

### 10.3 选择型 follow-up

- BT 路径、媒体分类、TMDB 候选、目录选择必须做成真正的“可选项列表”
- 列表项不允许只有内部术语，要带简短解释
- 选项数超过 5 时，要定义分页或折叠策略

### 10.4 状态 / inspect / list 型消息

- 状态型消息优先突出“当前状态”和“下一步”
- inspect / list 型消息要减少段落噪音，强调摘要、计数和关键命令

### 10.5 Content Budget

- 关键消息首屏默认只保留 4 块：标题、摘要、主体、动作。
- 主体区默认不超过 5 行；超出时进入展开 / 二段消息 / 分页。
- 动作区默认不超过 3 个主动作；更多选项进入分页或“查看更多”。
- 搜索候选默认首屏不超过 3 个；更多候选需要明确分页或继续查看动作。

### 10.6 State Coverage

所有关键消息都要定义以下状态，不允许只画 happy path：

- loading / waiting
- empty / no result
- unavailable / capability missing
- pending / waiting confirm
- expired / stale
- success / done
- failure / retry advice

## 11. Channel Rollout

### Phase 1

- 先做一条完整纵切：`搜索 -> 选择 -> 下载确认 -> 状态刷新`
- 收口 shared delivery model
- Telegram 上线 inline buttons
- 四渠道同步升级文本排版与 fallback 语义

### Phase 2

- 扩到 `导入确认`、BT follow-up、raw BT 目录选择、cleanup
- 补齐过期、重复点击、无结果、分页、取消等非 happy path
- 收敛命令帮助页与错误提示页

### Phase 3

- 对已经跑通的纵切再做 Feishu card message 与 action callback
- 扩到 watchlist、btsub、命令帮助和常见设置命令
- 仅在 shared runtime 语义已经稳定后再做更强视觉卡片化

## 12. Files Likely In Scope

- `app/runtime/delivery.py`
- `app/bot/telegram_runtime_adapter.py`
- `app/bot/telegram_delivery_runtime.py`
- `app/bot/feishu_adapter.py`
- `app/clients/feishu.py`
- `app/bot/wecom_adapter.py`
- `app/bot/personal_wechat_text.py`
- `app/services/search_reply_formatter.py`
- `app/services/add_to_downloader.py`
- `app/services/get_download_status.py`
- 相关 follow-up runtime / builder / tests
- `docs/GETTING_STARTED.md`
- `docs/ARCHITECTURE.md`
- 新设计或计划文档

## 13. Testing

- 文本 renderer golden-style tests：4 渠道都要有
- Telegram button payload tests：按钮数量、callback_data、fallback 文本
- Telegram callback round-trip tests：点击按钮后仍走现有 shared runtime
- Feishu card payload tests：header / section / action schema
- Feishu action callback tests：action -> shared runtime query
- 回归测试：现有文本命令路径继续可用

## 14. Risks

1. 把交互逻辑散到各渠道 adapter，导致 shared runtime 分叉。
2. 只做 Telegram 按钮，不先收口 shared action model，后续 Feishu 会重写一遍。
3. 过度追求视觉卡片，反而让 WeCom / personal WeChat 文本变长变难抄。
4. callback payload 设计不稳，会引入状态漂移或错误点击。

## 15. Not In Scope

- 不做 Web UI
- 不做群聊工作流
- 不在本轮引入数据库 schema 变更
- 不重做 shared private-chat runtime 主链语义
- 不为 WeCom / personal WeChat 强行造伪按钮

## 16. Success Criteria

1. 仓库里存在一份明确的多渠道消息交互计划，而不是只有效果图。
2. Telegram 搜索选择、确认、状态刷新至少一批关键流支持真实按钮。
3. Feishu 有明确的 card 化路线和落地边界，不再只停留在效果图。
4. WeCom / personal WeChat 拿到统一文本卡片排版，不比今天更难操作。
5. 所有按钮动作都仍能回到同一套 shared runtime 语义。
6. 任一关键动作在“按钮”和“文本命令”两条路径上的结果完全一致。
7. 关键消息有明确的内容预算、分页策略和非 happy path 定义。

## 17. AUTOPLAN REVIEW REPORT

### Intake

- Base branch：`main`（GitHub remote 已确认）
- Restore point：`/tmp/luminarr-message-interaction-autoplan-restore-20260429-013407.md`
- Existing plan status：此前没有针对“消息排版 / 卡片 / 按钮 / 选择流”的正式计划，只有视觉稿和零散的 delivery 骨架
- UI scope：`yes`
- DX scope：`no`
  - 这份计划谈的是终端用户在私聊里的消息体验，不是开发者 API / CLI / SDK 体验

### Phase 1 — CEO Review

#### 0A. Premise Challenge

本计划的核心前提有 4 个：

1. 用户真正要买单的是“更快读懂并更少输错命令”，不是“消息更像海报”。
2. 四渠道不需要长得一样，但必须共享同一业务语义。
3. Telegram 应该先吃到真实按钮，因为当前仓库已经有 callback plumbing。
4. Feishu 值得做 card，但不能早于 shared action model 稳定。

结论：

- 前提 1、2、3 成立，且和现有代码真相一致。
- 前提 4 也成立，但原始草案里对 rollout 还不够严格，容易先追视觉、后补闭环；已在本轮改成“先做完整纵切，再扩卡片能力”。
- Premise gate 说明：由于当前运行环境没有 AskUserQuestion UI，本轮将用户在 `2026-04-29` 明确提出的方向视为已确认前提：要系统规划消息排版、卡片化、Telegram 按钮、Feishu 可行性，以及确认 / 选择流的统一体验。

#### 0B. What Already Exists

| 子问题 | 已有代码 / 资产 |
| --- | --- |
| 跨渠道消息骨架 | `app/runtime/delivery.py` |
| 搜索消息 delivery builder | `app/services/search_reply_formatter.py` |
| 下载确认 delivery builder | `app/services/add_to_downloader.py` |
| 状态 delivery builder | `app/services/get_download_status.py` |
| Telegram callback plumbing | `app/bot/telegram_runtime_adapter.py` |
| Feishu 文本入口 | `app/bot/feishu_adapter.py` + `app/clients/feishu.py` |
| WeCom 文本回包 | `app/bot/wecom_adapter.py` |
| personal WeChat 文本收发 | `app/bot/personal_wechat_text.py` |
| 视觉方向 | `docs/assets/luminarr_visual_specs.md` + 4 张渠道效果图 |

#### 0C. Dream State

```text
CURRENT
  文本为主，少量 DeliveryItem，Telegram 能接 callback 但不发按钮
    ->
THIS PLAN
  同一语义模型 + 统一排版规则 + Telegram 完整纵切按钮化 + 其他渠道强文本 fallback
    ->
12-MONTH IDEAL
  Telegram / Feishu 渐进增强交互，WeCom / personal WeChat 保持高可读文本，四渠道共享同一审批与选择心智模型
```

#### 0C-bis. Implementation Alternatives

| Approach | Coverage | Effort | Risk | Verdict |
| --- | --- | --- | --- | --- |
| A. Shared intent + per-channel renderer | 高 | 中 | 中 | 采用 |
| B. Telegram / Feishu 各做各的 | 中 | 中 | 高 | 拒绝，易分叉 |
| C. 只美化文本 | 低 | 低 | 中 | 拒绝，浪费 Telegram / Feishu 能力 |

#### 0D. Mode-Specific Analysis

- 模式：`SELECTIVE EXPANSION`
- 自动批准的扩展：
  - 内容预算规则
  - 非 happy path 状态矩阵
  - rollout 从“按渠道堆能力”改成“按完整纵切交付”
- 明确 deferred：
  - WeCom / personal WeChat 真按钮
  - Web UI
  - 群聊工作流

#### 0E. Temporal Interrogation

- Hour 1：先统一消息语义，不然任何按钮都是糖衣。
- Hour 6：把 Telegram 搜索 / 选择 / 确认 / 状态闭环打通。
- Day 2 以后：再决定 Feishu card 是否跟进，以及跟到哪个动作深度。

#### 0F. CEO Conclusion

- 计划值得做。
- 但方向必须从“好看”修正为“更快完成关键动作”。
- 计划已吸收这一修正。

#### Error & Rescue Registry

| 风险 | 用户会看到什么 | Rescue |
| --- | --- | --- |
| 按钮和文本命令语义不一致 | 同一个动作在不同入口结果不同 | 所有动作先映射回 shared query，再进入 runtime |
| 候选信息过载 | 一屏看不完，用户不敢选 | 内容预算 + 分页 + 首屏只保留前 3 个 |
| 先做卡片、后补闭环 | 有些地方能点，有些地方还得猜命令 | rollout 改成完整纵切优先 |
| 视觉稿超出产品真相 | 用户以为已有某功能 | 视觉稿只能表达已实现或本计划内功能 |

#### Failure Modes Registry

| Failure mode | Severity | Mitigation |
| --- | --- | --- |
| 四渠道心智模型分裂 | high | 强制共享动作语义与 fallback 语义 |
| Telegram callback payload 不稳定 | high | 使用稳定动作 ID / payload 约束 |
| Feishu 过早卡片化导致重复实现 | medium | 放到 Phase 3 |
| 文本 fallback 被卡片设计挤压 | high | 文本渠道继续作为一等交付面 |

#### Dream State Delta

- 本计划能把仓库从“有视觉稿、少量文本卡片化、无统一交互计划”推进到“有明确语义模型、明确排期、明确 fallback 策略”。
- 本计划还不能直接得到所有渠道的富交互一致体验；Feishu 仍是后续阶段，WeCom / personal WeChat 则明确保持文本优先。

#### CEO DUAL VOICES — CONSENSUS TABLE

| Dimension | Primary review | Codex | Consensus |
| --- | --- | --- | --- |
| Premises valid? | yes | yes | CONFIRMED |
| Right problem to solve? | yes | yes | CONFIRMED |
| Scope calibration correct? | yes, after tightening rollout | mixed before fix | CONFIRMED after revision |
| Alternatives sufficiently explored? | yes | yes | CONFIRMED |
| Competitive / market risks covered? | partial | partial | DISAGREE |
| 6-month trajectory sound? | yes, if shared model first | warns against UX fragmentation | CONFIRMED with caveat |

#### CEO completion summary

| Item | Verdict |
| --- | --- |
| Problem choice | correct |
| Scope | correct after tightening |
| Biggest risk | fragmented multi-channel UX |
| Recommended focus | complete one vertical slice before expanding channels |

**Phase 1 complete.** Codex: `5` concerns. Claude subagent: unavailable in current session policy. Consensus: `5/6` confirmed, `1` disagreement surfaced.

### Phase 2 — Design Review

#### Design Scope

- Existing design truth examined:
  - `docs/assets/luminarr_visual_specs.md`
  - `README.md` channel card assets
  - `DeliveryItem` text renderer outputs
- Conclusion:
  - 有视觉方向，但缺少消息内容预算、状态矩阵、动作一致性规则。
  - 这些已回填到本计划。

#### Design Litmus Scorecard

| Dimension | Score | What was missing | Fix applied |
| --- | --- | --- | --- |
| 信息层级 | 8/10 | 之前缺内容预算 | 新增 `10.5 Content Budget` |
| 动作清晰度 | 8/10 | 按钮 / 命令双路径风险 | 新增一一对应约束 |
| 状态覆盖 | 9/10 | 原草案偏 happy path | 新增 `10.6 State Coverage` |
| 渠道差异策略 | 8/10 | rollout 过于按渠道而不是按闭环 | Phase 1-3 重排 |
| 选择负担控制 | 7/10 | 候选过多时策略不明 | 新增分页 / 首屏预算 |
| 视觉一致性 | 8/10 | 有稿无规则 | 统一标题/摘要/主体/动作四块 |
| 可实施性 | 8/10 | Feishu 提前介入风险 | 推迟到 Phase 3 |

#### Design findings

1. 原计划最大设计漏洞不是“卡片不够美”，而是缺少强硬的首屏预算。已补。
2. 搜索和选择流必须默认走“更少候选、更快确认”，不能把聊天窗口做成表格。已补。
3. “按钮优先 + 文本 fallback”只能成立在两条路径结果完全一致的前提下。已补。

#### Design voices

- Codex design challenge：
  - 警告“整齐的长文本”不等于可用卡片
  - 警告搜索流决策过载
  - 警告 rollout 若只追按钮会交付半成品
- Claude subagent：unavailable

**Phase 2 complete.** Codex: `3`核心 UX concerns absorbed. Claude subagent: unavailable. Consensus: `6/7` confirmed, `1` disagreement remains around long-term channel uniformity.

### Phase 3 — Engineering Review

#### Scope challenge

实际代码阅读表明，这不是从零开始的新系统，而是已有 delivery 骨架的收口问题。真正需要锁死的是“shared action model 不分叉”，而不是重写四个渠道 adapter。

#### Architecture ASCII Diagram

```text
private_chat_runtime query semantics
              ^
              |
   action translator / callback mapper
              ^
              |
 shared DeliveryItem + DeliveryAction model
      /            |              \
     /             |               \
Telegram      Feishu         Text fallback renderers
renderer      renderer       (WeCom / personal WeChat / Feishu fallback)
  |              |                     |
send_message  Feishu API          current text send paths
+ inline kb   + card payload      + current XML / text / poll senders
```

#### What already exists

| Layer | Current asset |
| --- | --- |
| Shared presentation model | `app/runtime/delivery.py` |
| Search delivery builder | `app/services/search_reply_formatter.py` |
| Approval delivery builder | `app/services/add_to_downloader.py` |
| Status delivery builder | `app/services/get_download_status.py` |
| Telegram callback ingress | `app/bot/telegram_runtime_adapter.py` |
| Feishu text transport | `app/clients/feishu.py` |
| WeCom reply transport | `app/bot/wecom_adapter.py` |
| personal WeChat reply transport | `app/bot/personal_wechat_text.py` |

#### Code quality / architecture findings

1. `DeliveryAction` 目前只有 `label / hint / kind`，它是文本动作模型，不是稳定交互模型。必须扩成能表达动作 ID、payload、文本 fallback 的结构。
2. Telegram adapter 已能接 `callback_query`，这是最好的落点；不要把 callback 语义埋进 service。
3. Feishu 当前 transport 只有 `send_private_text()`。如果要做 card，应该新增明确的 card send path，而不是在 text path 上混条件。

#### Section 3 — Test Review

已生成测试计划 artifact：

- [docs/plans/2026-04-29-message-interaction-and-card-delivery-test-plan.md](/home/alex/projects/luminarr/docs/plans/2026-04-29-message-interaction-and-card-delivery-test-plan.md)

Test diagram 结论：

- 新增 UX flow：
  - Telegram 搜索选择按钮
  - Telegram 确认 / 取消按钮
  - Telegram 状态刷新按钮
  - Feishu card action
- 现有代码已覆盖文本 renderer，但尚未覆盖真正的按钮 / card payload round-trip。
- 最大测试缺口不是样式，而是“按钮点击与手输命令完全等价”。

#### Performance / operational findings

- 性能风险低，消息体规模小。
- 主要运行风险是 payload 设计和 callback 语义不稳，不是吞吐。
- 部署风险可控：无 schema 变更；Feishu card 仅增加 API payload 复杂度。

#### Failure modes registry

| Failure mode | Severity | Engineering mitigation |
| --- | --- | --- |
| callback 点击后进入另一条业务语义 | critical | callback 统一翻译回 shared query |
| button path 覆盖 text path | high | text path tests 继续保留 |
| Feishu card 与 text fallback 字段不一致 | high | 同一 DeliveryItem 派生两种渲染 |
| 选择项过长导致 Telegram / Feishu UI 塌陷 | medium | 内容预算 + 截断 / 分页 |

#### Eng completion summary

| Dimension | Verdict |
| --- | --- |
| Architecture sound? | yes, if shared action model first |
| Test coverage sufficient? | not yet, but plan artifact now explicit |
| Performance risk | low |
| Security / correctness risk | medium, concentrated in callback mapping |
| Deployment risk | manageable |

#### ENG DUAL VOICES — CONSENSUS TABLE

| Dimension | Primary review | Codex | Consensus |
| --- | --- | --- | --- |
| Architecture sound? | yes with shared model | yes with caveats | CONFIRMED |
| Test coverage sufficient? | not yet | not yet | CONFIRMED |
| Performance risks addressed? | mostly | mostly | CONFIRMED |
| Security threats covered? | partial | partial | DISAGREE |
| Error paths handled? | now explicit in plan | warns half-finished rollout | CONFIRMED after revision |
| Deployment risk manageable? | yes | yes | CONFIRMED |

**Phase 3 complete.** Codex: `5` concerns reused across UX/eng. Claude subagent: unavailable. Consensus: `5/6` confirmed, `1` disagreement remains around long-term callback safety details.

### Phase 3.5 — DX Review

Skipped. No developer-facing product scope detected.

### Cross-Phase Themes

1. **Shared semantics before channel polish**
   - Flagged in CEO, Design, Eng.
   - Highest-confidence theme. If this slips, the feature becomes four partial UIs.

2. **Vertical slice before broad rollout**
   - Flagged in CEO and Design.
   - Do not ship “Telegram has buttons now” unless search -> choose -> confirm -> status forms a full usable loop.

3. **Text fallback is a first-class surface**
   - Flagged in Design and Eng.
   - WeCom / personal WeChat are not temporary leftovers; their text UX must stay excellent.

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | CEO | Use shared intent + per-channel renderer | Mechanical | P1 + P5 | Reuses existing delivery skeleton and avoids channel forks | Per-channel bespoke implementations |
| 2 | CEO | Keep Telegram first, Feishu later | Taste | P3 | Telegram already has callback ingress; Feishu card path is still transport-only | Parallel Telegram+Feishu rollout |
| 3 | CEO | Preserve text fallback as first-class | Mechanical | P1 | Two channels will remain text-first for the foreseeable future | Rich-only interaction |
| 4 | Design | Add content budget rules | Mechanical | P5 | Prevents “neater long text” from pretending to be card UX | Purely aesthetic cardification |
| 5 | Design | Add non-happy-path state matrix | Mechanical | P1 | Approval and selection flows are high-risk; missing stale/expired states would break trust | Happy-path-only mocks |
| 6 | Design | Limit candidate density on first screen | Mechanical | P3 | Search is a choice surface, not a dump of metadata | Full-detail candidate walls |
| 7 | Eng | Map every button back to shared query semantics | Mechanical | P5 | Prevents divergent business logic between click and text paths | Separate callback-only business handlers |
| 8 | Eng | Create dedicated test-plan artifact | Mechanical | P1 | The core risk is behavioral drift, not visual polish | Ad hoc test notes in chat only |
| 9 | Eng | Sequence rollout by vertical slice, not by channel | Taste | P3 | Full-flow integrity matters more than early channel screenshots | Channel-first rollout |
| 10 | Eng | Skip DX review | Mechanical | P3 | This is end-user chat UX, not developer-facing DX | Forcing devex framing onto user flows |
