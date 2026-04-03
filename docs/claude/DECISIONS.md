# docs/DECISIONS.md (v18)

> 目的：记录本项目已经拍板的关键决策，防止后续开发中反复摇摆。
> 原则：只记录“已决定”的内容，不记录讨论中的想法。
> 备注：当旧决策与新决策冲突时，以编号更大的条目为准。

---

## D-001 项目定位：只做垂直媒体自动化 Harness
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  Luminarr 只专注这一条链路：
  搜索 -> 下载 -> 入库 -> 刷新媒体库 -> 状态查询 -> 追更。
- **不做**：
  - 通用 AI 助手
  - 通用办公自动化
  - 多领域工具平台
  - 一开始就做成大而全平台
- **原因**：
  保持边界清晰、可逐步推进、可长期维护。

## D-002 交互方式：用户自然语言，内部结构化执行
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  用户侧保持自然语言体验；
  系统内部必须转换为结构化意图、工具调用和工作流推进。
- **原则**：
  - 自然语言 != 模型自由发挥
  - 模型只负责理解、补充、组织回复
  - 副作用动作必须由系统显式执行

## D-003 底座路线：自建极简 runtime
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  v1 采用自建极简底座，不直接依赖通用 agent runtime。
- **原因**：
  项目范围窄，自建足够且更易长期维护。

## D-004 渠道策略：Telegram 主线，微信后置
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  Telegram 是当前唯一主验收渠道；微信保留为后续辅助入口。

## D-005 当前主线固定组件
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  当前主线固定为：
  - Telegram
  - TMDB
  - Prowlarr
  - Transmission
  - Emby
  - SQLite
  - Docker Compose
- **补充**：
  qBittorrent、Jellyfin 不进入当前主线文档与最近开发顺序。

## D-006 工具面固定为 6 个核心工具
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  只保留：
  - `search_media`
  - `add_to_downloader`
  - `get_download_status`
  - `import_to_library`
  - `refresh_media_server`
  - `manage_watchlist`

## D-007 路径设计：统一公共根 `/data`
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  相关容器内部统一使用 `/data` 视图。
- **原因**：
  便于硬链接、调试和长期维护。

## D-008 硬链接原则：同一文件系统、默认不自动 copy
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  - 硬链接优先
  - 不跨文件系统假设
  - copy fallback 不作为默认路径
  - copy fallback 必须审批

## D-009 数据库策略：SQLite 继续作为唯一主线数据库
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  v1 继续使用 SQLite，保持单实例写入。

## D-010 项目记忆：靠仓库文件，不靠聊天线程
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  项目的长期记忆依赖：
  - `docs/DECISIONS.md`
  - `docs/NEXT_STEP.md`
  - `docs/STATUS.md`
  - `README.md`
  - `AGENTS.md`

## D-011 当前开发方式：一次只做一个小目标
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  每次任务必须是小范围、可测试、可回滚、可写清 Done when 的目标。

## D-012 当前开发环境
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  Windows + Codex Desktop + Ubuntu WSL，仓库放在 WSL 内。

## D-013 refresh 闭环：import 成功后触发 Emby refresh
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  - 当前 refresh 路径固定为 Emby-only
  - 仅在 import 成功后触发
  - refresh 失败不回滚 import 成功

## D-014 本地联调基线：WSL 独立 Transmission + Emby 测试栈
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  WSL 中使用独立测试栈做 import/refresh 联调，不替代 NAS 正式环境。

## D-015 当前不做入库重命名
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  当前阶段 `import_to_library` 只做硬链接导入与刷新，不引入命名规范化。

## D-016 最小持久化基线：候选映射 + job_event
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  - 搜索候选映射持久化到 SQLite
  - `job_event` 记录 import -> refresh 关键事件
  - 选择序号时优先走内存，缓存缺失再回读 SQLite

## D-017 TMDB-first 搜索基线
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  - parser-first 规范化
  - TMDB 可用时先做 movie lookup
  - 搜索顺序固定为：
    1. English title + year
    2. original title + year
    3. normalized original query（仅 TMDB 不可用或无命中时）
  - 中文海报卡片文本前置，候选编号格式保持不变

## D-018 import 显式 approval 交互
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  - `import <id/hash>` 只进入 pending
  - `confirm <id/hash>` 才执行导入副作用
  - `approval_record` 维持 pending/approved 最小协议
  - 重复/过期 confirm 必须确定性拒绝

## D-019 import confirm 最小 lease/version 防重放协议
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  - `approval_record` 增加 `lease_version`、`executed_version`
  - `import` 进入 pending 时推进当前 lease
  - `confirm` 只允许执行当前 lease
  - stale replay 在重启后必须被确定性拒绝

## D-020 并发调度哲学：只读可并发，副作用串行
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  - 工具契约必须显式声明 `concurrency_safe`
  - 只读 / 纯查询工具允许安全并发
  - 有副作用工具必须串行进入 workflow 主线
  - 同一 job 的副作用路径不得并发
- **原因**：
  提升响应速度，但不牺牲副作用安全边界。

## D-021 LLM 物理异常恢复：采用响应式恢复，而非把底层崩溃暴露给用户
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  对 `413 Payload Too Large`、`max_output_tokens` 截断等物理异常，系统后续应支持：
  - 激进上下文折叠
  - 保留 `system_base + project_rules + current_job_context`
  - 同轮次透明重试
- **说明**：
  该方向已在主用户搜索路径落地最小可用形态（同轮一次 compact-and-retry + 用户安全降级文案）。
- **原因**：
  模型物理异常不应直接污染用户体验。

## D-022 模糊查询隔离：允许只读 Explore Agent / Explore Subflow
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  对于高歧义查询，可使用只读探索子流程来做：
  - TMDB/Prowlarr 对比
  - 多轮澄清文案
  - 海报比对
- **边界**：
  不得写主 workflow 状态，不得执行副作用。
  只有最终确认的结构化结果可写回主状态机。
- **说明**：
  这是已采纳方向，当前尚未实现。

## D-023 审批唤醒后的上下文重建
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  当任务从 pending approval 被 `confirm` 唤醒时，执行阶段必须：
  - 清空冗余历史
  - 从持久化状态重建微型执行上下文
  - 不依赖旧的自由对话历史作为执行内存
- **原因**：
  降低执行阶段出错概率，并减少历史污染。

## D-024 低成本挫败感短路
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  在 Parser 层增加低成本规则检测：
  - 不对
  - 停
  - 重来
  - 换一个
  - 算了
  - 取消
- **行为**：
  在澄清 / 选择 / pending-approval 阶段触发时，优先走 deterministic reset/cancel，而不是继续消耗 LLM 回合。
- **原因**：
  优秀的 harness 必须知道什么时候“放弃使用 AI”。

## D-025 路线重排：watchlist 不再是最近一步
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  当前最近一步不再是 watchlist。
  正确顺序调整为：
  1. durable Telegram de-dup
  2. durable `jobs.version + lease_owner + lease_until`
  3. approval-wake context rebuild
  4. frustration/reset short-circuit
  5. explicit pre-dispatch approval for `add_to_downloader`
  6. 之后再回到 watchlist baseline
- **原因**：
  先补控制层，再做新业务面。

## D-026 文档优先级规则
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
  防止 Codex 被互相冲突的文档带偏。

## D-027 execution hygiene baseline 的最小落地形状
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  当前 execution hygiene baseline 按最小可用形状落地为：
  - `telegram_updates` 作为 Telegram message de-dup 的持久化真相源
  - `jobs` 先只承接 import approval wake/replay 所需的最小真相：
    - `version`
    - `lease_owner`
    - `lease_until`
    - `chat_id/user_id/task_ref/task_id/task_hash/state`
  - `confirm <id/hash>` 优先从持久化 `job + approval_record` 重建微型执行上下文
  - frustration/reset 当前只覆盖：
    - 选择窗口 reset
    - pending import approval cancel
- **原因**：
  先用最小真相源补齐执行卫生，不把当前仓库过早拉成完整 workflow 平台。

## D-028 downloader 显式 approval 基线已并入主线
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  - numeric select 不再直接 dispatch 到 Transmission
  - `add_to_downloader` 必须先进入 pending approval
  - `confirm <id/hash>` 必须可基于持久化 workflow truth 确定性路由到 downloader 或 import approval wake
  - downloader approval 也采用最小 lease/version 防重放
  - `jobs` 扩展承接 downloader approval wake/replay 所需的最小 payload truth
  - frustration/reset 在 pending approval 阶段也必须覆盖 downloader cancel
- **原因**：
  downloader dispatch 同样属于副作用路径，必须与 import approval 保持一致的执行边界和重放纪律。

## D-029 watchlist 最小手动基线已并入主线
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  - `manage_watchlist` 在当前阶段以最小手动基线落地：
    - SQLite 持久化真相（`watchlist_item`）
    - Telegram `watchlist` / `想看` 的 add/list/remove/clear
  - watchlist 在当前主线不得触发 downloader/import side effects
  - watchlist 不引入 auto-download，不引入 scheduler
- **原因**：
  先补齐最小业务面闭环，同时保持副作用边界与执行卫生稳定。

## D-030 pending approval timeout 基线已并入主线
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - `approval_record` 增加 pending timeout 持久化真相：`expires_at`
  - downloader/import 的 pending approval 在 `confirm <id/hash>` 时必须检查超时
  - 过期 pending confirm 必须确定性拒绝，并收敛为 cancelled 真相（`approval_record + jobs`）
- **原因**：
  pending approval 若无限期有效会破坏控制层可预期性；timeout 是最小且必要的执行卫生补齐。

## D-031 LLM 物理异常恢复最小基线已并入主线
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - 在主用户搜索路径对 `413` 与 truncated-style 物理异常做确定性检测
  - 同轮仅重试一次，并使用 compact 后的最小执行上下文
  - 若重试后仍是物理异常，返回用户安全文案，不直接暴露原始后端错误
- **原因**：
  以最小改动兑现 D-021 的执行目标，同时避免扩大到副作用路径与额外复杂性。
- **验证**：
  已通过手工 fallback 验收（重试次数为 2，最终返回安全降级文案）。

## D-032 clarification-stage frustration/reset 最小覆盖已并入主线
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - 在现有 Telegram 文本路由中，澄清阶段挫败词（`不对/停/重来/换一个/算了/取消`）已确定性短路，不再继续额外 LLM 回合
  - 当当前 chat 处于“搜索无候选后的澄清 pending”时，挫败词优先走 clarification reset
  - pending downloader/import approval cancel 的既有行为保持不变
  - 候选窗口 reset 的既有行为保持不变
- **原因**：
  用最小改动补齐 D-024 在“澄清阶段”的最后缺口，同时不引入新协议和额外复杂性。
- **验证**：
  已通过 targeted pytest 与手工脚本验收。

## D-033 read-only concurrency-safe execution policy 最小基线已并入主线
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - 增加最小 runtime execution policy 声明：显式标记 `concurrency_safe`
  - `search_media`、`get_download_status`、`watchlist list` 作为只读路径可并发
  - `add_to_downloader`、`import_to_library`、`confirm`、`watchlist` 写操作与 reset/cancel 路径保持串行
  - Telegram 现有命令词与成功/失败文案保持不变
- **原因**：
  以最小改动兑现 D-020，提升只读路径吞吐同时不破坏副作用安全边界。
- **验证**：
  已通过 `pytest` 全量回归与手工并发策略脚本验收。

## D-034 ambiguous-title isolated read-only exploration 最小基线已并入主线
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - 在 `search_media` 主读路径中，对“无年份 + 高歧义结果”增加最小只读探索澄清分支
  - 澄清分支只返回只读参考候选文本，不写入 downloader/import 审批状态，不触发任何副作用动作
  - 在澄清 pending 阶段，Telegram 数字选择被确定性拦截，避免误入下载选择路径
  - 既有命令词与 downloader/import 成功失败文案保持不变
- **原因**：
  以最小改动落实 D-022，先补齐高歧义查询隔离边界，再继续补控制层耐久性缺口。
- **验证**：
  已通过 targeted pytest 与手工临时脚本验收（脚本已按规范清理）。

## D-035 渠道扩展策略：WeChat 作为平行 channel adapter，后期接入
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - Telegram 保持唯一主验收渠道（D-004 不变）
  - 未来接入微信时，采用**平行 channel adapter 架构**，不替换 Telegram，不改动现有 parser/router/workflow/tools 层
  - channel adapter 层只负责：消息收发、消息格式标准化、reply 路由回对应渠道
  - 底层协议选型：iLink/ClawBot 个人微信 HTTP 长轮询 API（即 `wechat-clawbot` PyPI 包所封装的协议），不依赖企业微信/Webhook/微信桌面客户端
  - WeChat adapter 实现时必须复用现有 parser → router → workflow → tools 全链路，不得为 WeChat 单独维护一套业务逻辑
  - WeChat adapter 在当前阶段**不排入开发计划**，等主线控制层稳定后再启动
- **架构示意**：
  ```
  [Telegram long-poll]  [WeChat iLink long-poll]   ← channel adapters（平行）
          ↓                       ↓
      消息标准化 → Parser → Router → Workflow → Tools
          ↓                       ↓
      Telegram reply          WeChat reply
  ```
- **不做**：
  - 为 WeChat 单独写一套 intent parser
  - 企业微信 WeCom 接入
  - 微信群聊支持（仅私聊，与 Telegram 对齐）
  - 引入 OpenClaw / nanobot 作为 runtime 依赖
- **参考实现**：`wechat-clawbot`（PyPI）、`@tencent-weixin/openclaw-weixin`（npm，了解协议用）
- **原因**：
  微信是国内主要沟通渠道，但引入成本低、协议成熟，适合在主线稳定后以最小改动平行接入。

## D-036 本地集成测试栈：WSL Docker Transmission + Emby
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - 开发环境为 Windows + WSL（Ubuntu），仓库在 WSL 内，Codex 在 WSL 命令行交互
  - 本地集成测试栈通过 WSL 内 Docker Compose 运行，包含：
    - **Transmission**（下载器测试实例）
    - **Emby**（媒体服务器测试实例）
  - 测试栈配置见 `docs/TEST_ENV.md`（包含端点、路径、凭据占位）
  - 涉及 `import_to_library` / `refresh_media_server` / 硬链接的集成验证，必须在本地测试栈上运行，不得用 mock 替代
  - 硬链接要求下载目录与库目录在同一文件系统：WSL Docker 挂载路径必须满足此约束（见 `docs/TEST_ENV.md`）
  - 本地测试栈与 NAS 正式环境相互独立，不共享数据
- **原因**：
  硬链接行为无法通过纯 mock 验证，必须在真实文件系统上跑。WSL Docker 是当前最小可用的本地集成环境。

## D-037 下载后自动入库：取消手动 import confirm，保留下载选择确认
- **状态**：已决定
- **日期**：2026-04-03
- **替代**：D-018（局部覆盖，import 审批部分废弃；下载选择审批保留）
- **结论**：
  - 用户只需要确认一次：**选择哪个资源下载**（搜索结果选择 + 确认）
  - 下载完成后，系统自动执行：硬链接入库 → 刷新 Emby → 通知用户完成
  - 取消 `import <id>` / `confirm <id>` 的手动 import 审批交互
  - 下载选择审批（`add_to_downloader` 的 pending → confirm 流程）保留不变
  - 自动入库失败（如硬链接报错、Emby refresh 超时）必须通知用户，不得静默失败
- **后续影响**：
  - `import_to_library` 从用户触发改为 scheduler/monitor 触发
  - `approval_record` 的 import 相关协议可逐步移除（当前 pending 阶段完成后）
  - `jobs` 表中 import 状态流转改为自动推进
- **原因**：
  自动化流程应该对用户透明无感；手动 import confirm 是早期控制层补丁，现在有更完整的状态机可以取代它。

## D-038 剧集 / 动漫追更：后台自动监控 + 全链路通知
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - watchlist 从纯手动记录升级为**追更驱动源**
  - 后台 scheduler 定期检查 watchlist 中剧集 / 动漫的更新状态（TMDB episode 数据 + Prowlarr 资源可用性）
  - 发现新集数且资源可用时，自动触发搜索 → 选优质资源 → 投递下载（无需用户介入）
  - 资源选择规则（分辨率、字幕、做种数等）可配置，按规则自动选优，不再依赖用户手选
  - 全链路通知节点：
    1. 检测到新集数 → 通知"发现更新，正在搜索资源"
    2. 资源找到并投递下载 → 通知"已开始下载 SxxExx"
    3. 下载完成 + 入库完成 → 通知"已入库，可在 Emby 观看"
    4. 资源搜不到 → 通知"暂无资源，将在下次检查时重试"
  - scheduler 检查周期可配置，默认每小时一次
  - 剧集追更与电影搜索共用同一套工具链（`search_media` / `add_to_downloader` / `import_to_library` / `refresh_media_server`），不单独维护逻辑
- **不做**：
  - 不替代 Sonarr（不做 season pack 拆包、不做复杂命名规则引擎）
  - 不做 RSS 直接订阅（走 Prowlarr 聚合层）
- **原因**：
  追更是自托管影视自动化的核心场景，watchlist 不做追更就失去了大半价值。

## D-039 多下载器路由：PT 专用 + BT 专用，qBittorrent 后续加入
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - 下载器按类型路由，不混用：
    - **PT 下载器**：专用于 PT 站资源，保号需要，独立管理（当前主线：Transmission 保留为 PT 下载器）
    - **BT 下载器**：专用于公网 BT / 磁力资源（后续加入 qBittorrent 作为 BT 专用）
  - `add_to_downloader` 工具增加路由逻辑：根据资源来源（PT 站 vs 公网）自动选择下载器
  - 两个下载器的 `downloadDir` 必须都满足与库目录同一文件系统（硬链接约束）
  - qBittorrent 接入时机：待 Transmission 主线稳定、D-037 自动入库落地后再启动
  - 下载器配置在 `.env` / config 中独立维护，不硬编码
- **当前主线不变**：Transmission 仍是唯一下载器，直到 qBittorrent 接入任务明确启动
- **原因**：
  PT 下载器混用 BT 资源可能触发风控；分离路由是长期运营的必要条件。

## D-040 渠道扩展完整路线：企业微信 + 飞书 + 个人微信
- **状态**：已决定
- **日期**：2026-04-03
- **替代**：D-035（扩展，不废弃）
- **结论**：
  - 三条渠道全部采用**平行 channel adapter 架构**（与 D-035 架构相同），共用 parser/router/workflow/tools
  - 接入优先级（从易到难）：
    1. **飞书**：官方 Bot API + Webhook，文档最完善，API 设计最现代，优先接入
    2. **企业微信（WeCom）**：官方 Bot API + Webhook，稳定，无封号风险，第二接入
    3. **个人微信**：iLink 长轮询，需维持扫码会话，稳定性最弱，最后接入
  - 飞书支持消息卡片（Card），可做比 Telegram 更丰富的海报展示，接入时优先适配
  - 三条渠道均只支持私聊，不做群聊
  - 企业微信 / 飞书 Webhook 需要公网可达地址或内网穿透（部署时注意）
- **不做**：
  - 企业微信客服号接入（仅 Bot）
  - 飞书群机器人（仅私聊 Bot）
- **原因**：
  国内日常沟通以微信 / 飞书为主，三条渠道覆盖后使用场景完整。

## D-041 字幕自动翻译：无中文字幕时自动提取英文字幕并 AI 翻译
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - 入库完成后，自动检测媒体文件是否包含中文字幕
  - 如无中文字幕，自动触发字幕翻译任务：
    1. 从媒体文件中提取英文字幕（`.srt` / `.ass` / 内嵌字幕轨）
    2. 调用独立 AI 翻译提供商逐段翻译（支持配置，默认可用 DeepSeek / OpenAI）
    3. 将翻译结果写回为 `.zh.srt` 字幕文件，放在媒体文件同目录
    4. 触发 Emby refresh，使字幕被识别
  - 翻译任务是异步后台任务，不阻塞入库流程
  - 翻译完成后通知用户（渠道同入库通知）
  - 翻译提供商 API Key 独立配置，与主 LLM 配置分开
  - 字幕提取工具：`ffprobe` + `ffmpeg`（容器内依赖）
- **不做**：
  - 在线字幕库搜索（如 OpenSubtitles）—— 后续可选，当前只做本地提取翻译
  - 实时字幕翻译
- **原因**：
  大量英语影视资源缺乏中文字幕，自动翻译是显著提升观看体验的高价值功能。

## D-042 文件规范化 + 刮削：硬链接后重命名 + TMDB/Fanart 元数据写入
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - 硬链接入库后，立即对目标文件执行规范化重命名，格式完全符合 Emby / Jellyfin / Plex 元数据读取规格：
    - 电影：`电影名 (年份)/电影名 (年份).ext`
    - 剧集：`剧集名 (年份)/Season XX/剧集名 - SxxExx - 集标题.ext`
  - 重命名完成后执行刮削：
    1. 主数据源：TMDB（标题、简介、评分、演员、分类）
    2. 图片主数据源：Fanart.tv（海报、背景图、Logo）
    3. Fanart 无图时 fallback 到 TMDB 图片
    4. 将元数据写入 `.nfo` 文件（Emby / Jellyfin 标准格式）
    5. 将图片下载到媒体目录（`poster.jpg` / `fanart.jpg` / `logo.png`）
  - 刮削完成后触发 Emby refresh（复用 `refresh_media_server`）
  - 刮削任务是自动任务，不需要用户介入；失败时通知用户
  - Fanart.tv API Key 独立配置
- **硬链接约束不变**：重命名操作在硬链接目标（库目录）侧进行，源文件（下载目录）不改名
- **原因**：
  不规范命名会导致 Emby 无法正确识别媒体；刮削是入库闭环的必要组成部分。

## D-043 下载器资源与库文件关联监控 + 自动清理
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - 系统维护下载器任务与库文件的关联记录（`jobs` 表扩展或独立 `media_asset` 表）
  - 定期检查（scheduler）以下场景并自动处理：
    1. **Emby 库文件被删除**（用户看完手动删）→ 检测到对应库文件不存在 → 自动删除下载器中对应任务 → 通知用户"已同步清理下载器任务"
    2. **下载器任务已消失但数据库仍有记录**（手动在 TR/qB 中删除）→ 自动将数据库任务状态收敛为 `orphaned` → 定期清理
    3. **PT 做种保留策略**：PT 资源默认不因库文件删除而立即删除下载器任务（需保号），保留策略可配置（做种时长 / 做种比例）
  - 清理操作执行前记录日志，不静默删除
  - BT 资源无保号需求，库文件删除后可立即清理下载器任务
- **原因**：
  长期运行后下载器任务列表会积累大量过期条目；与库文件的关联监控是维护健康状态的必要机制。

---

## 附：更新模板

### D-XXX 标题
- **状态**：已决定 / 已废弃 / 已替换
- **日期**：YYYY-MM-DD
- **结论**：
- **原因**：
- **影响范围**：
- **替代项**：（如有）
