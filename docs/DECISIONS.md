# docs/DECISIONS.md (v41)

> 目的：只保留“当前仍然有效”的项目决策。
> 说明：旧的阶段推进记录、历史 next-step 迁移、旧验收备注已清理。
> 当前施工目标只看 `docs/NEXT_STEP.md`；当前实现状态只看 `docs/STATUS.md`；项目来龙去脉看 `docs/HISTORY.md`。

---

## D-001 项目定位
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  - Luminarr 只做 2–4 人自托管影视场景的垂直自动化 Harness。
  - 当前主线只服务“搜索 -> 下载 -> 入库 -> 刷新 -> 状态查询 -> 追更”。
  - 不做通用 AI 助手、通用办公自动化、通用 Agent 平台。
- **原因**：
  保持边界窄，才能长期稳定维护。

## D-002 交互模型
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  - 用户侧保持自然语言。
  - 系统内部必须转成结构化意图、确定性路由和显式副作用执行。
  - 自然语言体验不等于模型自由发挥。
- **原因**：
  用户要的是“像聊天”，系统需要的是“可控执行”。

## D-003 当前固定运行画像
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  当前主线固定为：
  - Telegram 私聊
  - TMDB
  - Prowlarr（当前主来源）+ 最小 BT WebSource（仅 BT 支线）
  - Transmission + qBittorrent
  - Emby
  - SQLite
  - Docker Compose
  - 单实例 / 单进程 / 单机
  - movie-first workflow
- **原因**：
  主线必须先固定，才能避免路线漂移。

## D-004 文档优先级
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  文档冲突时按以下顺序解释：
  1. `docs/DECISIONS.md`
  2. `docs/NEXT_STEP.md`
  3. `docs/STATUS.md`
  4. `README.md`
  5. `AGENTS.md`
- **原因**：
  防止新旧文档互相打架。

## D-005 PT / BT 主干边界
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - PT 主干承接正常观影需求，例如：
    - `我想看 X`
    - `追更 X`
    - `watchlist`
  - BT 主干承接直接 BT 需求，例如：
    - 原始 `magnet:?`
    - 明确“下载这个 BT / 下载这个磁力”
  - 分叉点必须在 parser / routing 入口，而不是到了后半段再临时判断。
  - PT 与 BT 从入口开始天然隔离。
- **原因**：
  两条链的目标不同，混在一起只会让代码和交互都失控。

## D-006 模型使用边界
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - parser-first，LLM-fallback。
  - 模型不负责：
    - 幂等
    - lease ownership
    - execution-result truth
    - approval re-validation
  - 背景恢复和 scheduler tick 不得依赖 LLM 调用。
  - 高歧义搜索允许只读探索辅助，但不得写主 workflow 真相或触发副作用。
- **原因**：
  模型适合辅助理解，不适合做账本和红绿灯。

## D-007 执行安全边界
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - `telegram_updates` 是 Telegram 去重真相源。
  - `jobs.version + lease_owner + lease_until` 是当前执行所有权真相源。
  - `confirm <id/hash>` 必须从持久化 `job + approval_record` 重建最小执行上下文。
  - 只读动作可标记 `concurrency_safe`；副作用路径必须串行。
  - 同一 job 的副作用不得并发；未持有 lease 时必须退出。
- **原因**：
  先保住副作用安全，再谈自动化提速。

## D-008 审批与导入纪律
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - `add_to_downloader` 和 `import_to_library` 都必须先进入 pending approval。
  - `approval_record` 维护 pending / approved / expired 的最小真相，并带 `lease_version / executed_version / expires_at`。
  - 重复、过期、stale `confirm` 必须确定性拒绝。
  - confirmed import 默认先走硬链接；跨文件系统失败时必须进入显式 copy-fallback pending，不得静默复制。
- **原因**：
  下载和导入都属于会改文件、改下载器状态的动作，必须有同样严格的闸门。

## D-009 当前媒体后半段
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - confirmed import success 后，当前媒体后半段固定为：
    - 规范化命名
    - metadata scraping（TMDB + Fanart.tv）
    - subtitle auto-translation（当前仅 `.srt`）
    - Emby refresh
  - refresh 失败不回滚 import success。
  - metadata / subtitle 失败必须显式记录并打印可读错误，但不回滚 confirmed import success。
- **原因**：
  入库成功是真相；刮削、字幕、刷新是后续增强动作。

## D-010 BT 分类后的后半段
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - BT 必须先做分类：`movie / series / anime / raw_bt`。
  - `movie / series / anime` 属于媒体型 BT：
    - 必须尝试做 TMDB 关联
    - 下载完成后复用现有媒体后半段
  - `raw_bt` 属于原始 BT：
    - 不做 TMDB
    - 不做 metadata / subtitle / refresh
    - 只允许走预设目录选择 -> 下载 -> 放置
    - 手动 `import <id/hash>` 必须确定性拒绝
- **原因**：
  媒体型 BT 和原始 BT 是两类完全不同的落地方式。

## D-011 下载器模型
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 下载器采用“实例 + 角色绑定”：
    - 配置定义多个实例
    - `pt_downloader` / `bt_downloader` 绑定实例名
  - 任务真相必须记住：
    - 当前任务是 PT 还是 BT
    - 当前任务类型是 `movie / series / anime / raw_bt`
    - 实际投递到哪个下载器实例
    - 该实例属于哪种协议
  - qBittorrent 当前已落地最小协议：
    - add torrent / magnet
    - get status
    - get import source
- **原因**：
  角色和实例分开，后面才不会因为换下载器就重写整条业务链。

## D-012 watchlist 与 BT subscription 当前边界
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - `watchlist` 当前是手动、持久化、无副作用基线。
  - `watchlist` 支持 `movie / series / anime`，但不做 auto-download。
  - `btsub` 当前已支持手动命令和最小后台 tick。
  - `btsub` 命中新资源后，仍必须走现有 downloader approval -> `confirm` 边界。
  - 当前不允许：
    - 自动 `confirm`
    - `raw_bt` subscription
    - 通用 scheduler 平台化
- **原因**：
  先让追更和订阅可控，再考虑更重的自动化。

## D-013 当前明确不做
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  当前主线不做：
  - Feishu / WeCom / personal WeChat
  - Jellyfin / Plex 并行主线支持
  - 通用 plugin / skill / MCP 平台化
  - React TUI / Web UI / 桌面端
  - Redis / MQ / PostgreSQL
  - 多机分布式部署
- **原因**：
  这些方向都会把项目从“可控自动化链”拉成“大平台”。

## D-014 BT 外部网站源
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 当前 BT 主干已在 Prowlarr 之外接入最小 `WebSource` baseline。
  - `WebSource` 只允许服务 BT 分流：
    - 直接 BT / magnet 搜索
    - BT 订阅 / 连续下载
    - BT 手动探索
  - `WebSource` 不得进入 PT 主链。
  - `Prowlarr + WebSource` 必须先经过共享 BT 来源适配层，再进入 BT 链路。
  - 外部网站源命中结果后，仍必须复用现有 downloader approval -> `confirm` -> dispatch 边界。
  - 第一阶段只允许静态 HTML + 直接 magnet / torrent 链接。
  - 第一阶段不接入 JS 渲染、CAPTCHA、强登录站。
- **原因**：
  BT 分流确实需要 Prowlarr 之外的资源来源，但不能反过来破坏 PT 主线。

## D-015 BT 站点规则定义与 BT-only read-only helper
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 外部 BT 网站源采用“项目内确定性站点规则定义”，不做通用 skill 平台。
  - 运行时主链仍由确定性代码负责：
    - 发请求
    - 解析页面
    - 统一候选字段
    - 校验链接
    - 去重
    - 进入既有审批链
  - 后续允许增加 BT-only read-only helper，用于：
    - 手动 BT 探索
    - 站点规则维护 / 修复辅助
    - HTML 到结构化候选的只读整理辅助
  - 该 helper 只允许存在于 BT 支线，且不得：
    - 写数据库
    - 写 approval / jobs / lease 真相
    - 直接 dispatch 下载器
    - 直接触发 import / refresh / 任何副作用
  - scheduler tick、`btsub run`、恢复逻辑不得依赖该 helper 或 LLM。
- **原因**：
  这里允许的是“BT 支线助手”，不是“通用 skill 平台”。

## D-016 本地集成验证基线
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - WSL Docker 的 Transmission + Emby 测试栈是正式本地集成验证基线。
  - `docs/TEST_ENV.md` 是该测试栈正式入口。
  - 涉及 `add_to_downloader` / `import_to_library` / `refresh_media_server` / 相关持久化协议的端到端任务，不得只靠 mock。
- **原因**：
  硬链接、下载器 RPC、媒体库刷新都要靠真实文件系统和真实接口验证。

## D-017 原始磁力入口后续增加“处理链”问询，而不是重新问协议类型
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 当用户直接发送 `magnet:?` 或明确要求“下载这个 BT / 磁力”时，系统仍先进入 BT 支线。
  - 当前该入口已增加一层最小问询，问的不是“PT 还是 BT”，而是：
    - `影视入库链`
    - `纯 BT 下载链`
  - 当用户选择 `影视入库链` 时：
    - 后续继续进入媒体型 BT 流程
    - 继续做 `movie / series / anime` 分类、TMDB 关联和媒体后半段
  - 当用户选择 `纯 BT 下载链` 时：
    - 后续继续进入 `raw_bt` / 纯 BT 流程
    - 不进入 TMDB、metadata、subtitle、refresh 链
  - 为兼容旧 follow-up，当前仍允许在该问询阶段直接回复：
    - `movie / series / anime`
    - `raw_bt`
    但这只是兼容捷径，不是新的主交互形状。
- **原因**：
  用户已经发的是磁力，协议层面本来就是 BT。这里真正需要分的不是协议，而是“后续按影视资源处理”还是“按纯 BT 资源处理”。

## D-018 纯 BT 下载链按单片资源优选，不复用影视资源规则
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 纯 BT 下载链不复用影视入库链的复杂规则。
  - 当前纯 BT 使用场景以单片资源为主，因此后续优选只需要围绕“单个资源规格是否足够出色”来做。
  - 纯 BT 优选后续可采用“确定性预过滤 + LLM 辅助优选”的形状：
    - 代码先做基础过滤：
      - 链接有效
      - 非重复
      - 标题命中
      - 单片资源基本条件成立
    - 再允许 LLM 在少量候选中做“哪个版本更值得下”的辅助判断
    - 最终是否投递，仍由项目自己的确定性代码决定
  - 纯 BT 连续任务允许后续扩展为“批量 / 区间 / 持续任务”，例如按编号范围持续补齐单片资源。
- **原因**：
  纯 BT 资源的目标不是做标准影视入库，而是选出一份更出色的单片版本。这里可以比影视主链更简单，但仍要保留可控边界。

## D-019 BT subscription 已采用共享确定性选源，不再盲拿第一个结果
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - `btsub run` 和后台 scheduler tick 必须共用同一个确定性选源 helper。
  - BT subscription 选源不再盲目拿“第一个可下载结果”。
  - 当前最小选源规则允许使用这些确定性信号：
    - 链接存在
    - 跳过 `last_seen_source`
    - 明确低质量标记过滤优先级
    - 标题里的基础分辨率信息
    - `seeders`
    - `size`
  - 当前这一步仍不是通用质量评分 / 规则引擎。
  - 命中结果后，仍必须复用现有 downloader approval -> `confirm` 边界。
- **原因**：
  先把 BT subscription 从“盲选第一个结果”收紧到可解释、可复用、无 LLM 依赖的最小确定性基线，再继续后续 BT 路线。

## D-020 pure BT 最小单片优选先落成确定性文本查询基线
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - pure BT 现阶段先只落地最小确定性单片优选基线，不引入额外多轮框架。
  - 当用户发送文本型直接 BT 请求，并显式带上查询词，例如：
    - `下载这个 BT Frieren S01E01`
    - `下载这个磁力 某作品 EP01`
    进入 `纯 BT 下载链` 并完成 `raw_bt` 目标目录选择后，系统允许：
    - 先用现有搜索源拿候选
    - 过滤无链接候选
    - 过滤标题不命中的候选
    - 过滤明显低质量候选
    - 过滤明显多集 / 合集 / 整季候选
    - 再用基础分辨率、`seeders`、`size` 做最小确定性排序
  - 命中后，仍必须复用现有 downloader approval -> `confirm` 边界。
  - direct `magnet:?` 的 pure BT 路径保持原样，不经过这层文本查询优选。
  - 这一步仍不进入 TMDB、metadata、subtitle、refresh，也不复用影视入库链规则。
- **原因**：
  先把 pure BT 的“文本型单片资源挑一个更像样的版本”补成最小可用基线，同时避免把媒体链规则、`btsub` 规则和新的站点接入混在同一步里。

## D-021 非 Telegram 私聊适配先做“渠道作用域整数 ID 投影”，不改现有真相表主键形状
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - 当前 `jobs / watchlist / bt_subscription / clarification / bt_pending / candidate_mapping / download_monitor` 这些真相边界继续保留现有整数 `chat_id / user_id` 形状。
  - 非 Telegram 私聊渠道如果拿到的是字符串会话标识或用户标识，必须先在适配层做**稳定、确定性、带渠道命名空间**的整数投影，再进入 shared private-chat text runtime 和既有 service。
  - 渠道名必须进入投影输入，避免不同渠道相同原始字符串发生撞号。
  - 原始外部标识只保留在渠道适配层，用于该渠道自己的回消息动作；不得把它直接塞进现有 SQLite 整数真相列。
- **原因**：
  这样能在不改审批、作业、候选缓存和持久化协议的前提下，先把 Feishu 私聊最小文本入口接进现有主链，保持 diff 最小且风险可控。
