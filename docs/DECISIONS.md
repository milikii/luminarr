# docs/DECISIONS.md (v27)

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

## D-035 clarification pending restart-durable 最小基线已并入主线
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - 澄清 pending 真相从“仅进程内内存”提升为“SQLite 持久化 + 内存快路径”双层形态（`clarification_state`，chat 维度）
  - `search` 空结果/高歧义澄清分支会写入澄清 pending 持久化真相
  - 搜索成功与澄清 reset 会确定性清除澄清 pending（内存与持久化同时收敛）
  - 澄清 pending 下数字选择拦截在重启后仍保持确定性行为
  - 既有命令词与 downloader/import 成功失败文案保持不变
- **原因**：
  以最小改动补齐“澄清状态重启后丢失”这个控制层耐久性缺口，不把方案扩展为通用 workflow 状态平台。
- **验证**：
  已通过 targeted pytest、全量 pytest、手工临时脚本验收（脚本按规范清理）。

## D-036 本地集成测试栈正式入主文档
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - WSL Docker 中的 Transmission + Emby 测试栈，正式作为本项目本地集成验证基线
  - `docs/TEST_ENV.md` 成为该测试栈的正式说明入口，记录端点、路径、配置占位与健康检查方法
  - 真实凭据不得写入仓库；`docs/TEST_ENV.md` 只保留占位说明，真实值放本地 `.env` / 配置
  - 涉及 `add_to_downloader` / `import_to_library` / `refresh_media_server` / 相关持久化协议的端到端任务，优先用该测试栈验收，不得只靠 mock
- **原因**：
  硬链接、下载器 RPC、媒体库刷新都依赖真实文件系统与真实接口，单元测试不能替代真实联调。

## D-037 新路线图并入主文档，但不改写当前 next step
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - `docs/claude` 中的阶段化路线可并入 `README.md` 与 `docs/STATUS.md`，作为后续路线说明
  - `docs/NEXT_STEP.md` 仍然只保留一个当前最小目标；当前目标继续是 Telegram callback workflow routing baseline
  - 在 callback routing 与其后剩余最小控制层缺口稳定前，不得提前启动自动入库、多渠道、多下载器、追更等阶段性能力
  - `README.md` 若描述完整自动化链路，必须明确区分“当前已实现主线”和“后续阶段路线”
- **原因**：
  需要吸收新文档里的长期方向，但不能让未来路线伪装成当前事实，避免开发顺序被大路线打乱。

## D-038 Telegram callback workflow routing 最小基线已并入主线
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - Telegram runtime 现在接受 callback update，并统一路由到现有文本命令共用的 workflow dispatcher
  - callback 去重继续复用持久化 `telegram_updates` 真相，按 `callback_query_id` 确定性去重
  - callback 路径不得绕过既有 downloader/import approval 边界、`jobs` 所有权、lease/version、防重放和 execution gate
  - callback 路径允许从 `effective_*` 或 callback 自带 message/user 上下文恢复 chat/user/message 信息；既有命令词与成功/失败文案保持不变
  - 当前 next smallest path 前进到 cross-filesystem import 的 copy fallback approval
- **原因**：
  先用最小改动补齐 Telegram 控制层最后一个明显缺口，并继续坚持“不复制业务逻辑、不放松副作用边界”的实现方式。
- **验证**：
  已通过 targeted pytest、全量 pytest、临时 `tmp_tests` 手工脚本验收（脚本已按规范清理）。

## D-039 cross-filesystem import 的 copy fallback approval 最小基线已并入主线
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - confirmed import 仍然默认先走硬链接，copy 不是默认路径
  - 当硬链接因 cross-filesystem 失败时，系统必须进入显式 copy-fallback pending，而不是静默自动 copy
  - 用户再次发送 `confirm <id/hash>` 后，才允许执行 copy 导入
  - copy-fallback pending 继续复用现有 approval / confirm / `jobs` 真相，并通过最小持久化上下文在重启后保持成立
  - 当前 next smallest path 前进到 completion-monitor / scheduler prerequisite
- **原因**：
  先补齐 import 链路最后一个明显的文件系统安全缺口，同时继续坚持“默认硬链接、不静默降级、不另起第二套工作流”的最小实现原则。
- **验证**：
  已通过 targeted pytest、全量 pytest、临时 `tmp_tests` 手工脚本验收（脚本已按规范清理）。

## D-040 completion-monitor / scheduler prerequisite 最小基线已并入主线
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - 当前阶段不引入通用 scheduler 平台，只先补最小 completion-monitor 真相
  - downloader dispatch 成功后，系统必须把真实下载任务登记到持久化 completion-monitor 账本（`download_monitor`）
  - `status <id/hash>` 在成功拿到真实下载状态时，必须同步更新该账本中的 observed truth
  - 第一次观察到下载完成时，系统必须追加确定性的完成事件（`downloader.completed_observed`），供后续自动化闭环复用
  - 当前 next smallest path 前进到 post-download auto import baseline
- **原因**：
  先补齐自动化闭环前最后一个“可持久化、可恢复、与聊天历史解耦”的运行时真相层，同时避免过早把仓库扩成通用 scheduler 平台。
- **验证**：
  已通过 targeted pytest、全量 pytest、临时 `tmp_tests` 手工脚本验收（脚本已按规范清理）。

## D-041 post-download auto import 最小基线已并入主线
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - 当前阶段允许“已观察到完成的下载”自动推进到现有 `import` approval-pending 路径
  - 自动推进必须继续复用现有 `import_to_library` / approval / `jobs` 真相，不能绕过 `confirm <id/hash>` 执行真实导入副作用
  - 自动推进不得破坏 cross-filesystem copy-fallback approval 规则；后续真实导入仍按原有安全边界执行
  - 当前 next smallest path 前进到 resource auto-selection rules
- **原因**：
  先补齐自动化闭环第一步，同时坚持“自动推进只到待确认，不直接做副作用执行”的最小实现原则，避免控制层边界退化。
- **验证**：
  已通过 targeted pytest、全量 pytest、临时 `tmp_tests` 手工脚本验收（脚本已按规范清理）。

## D-042 resource auto-selection rules 最小基线已并入主线
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - 已观察到完成的下载在自动推进到 `import` approval-pending 之前，必须先经过最小 deterministic resource auto-selection 规则
  - 当前最小规则只拦截明确低质量来源标记：`CAM` / `HDCAM` / `TS` / `HDTS` / `TC` / `SCR` / `WORKPRINT`
  - 命中规则时，系统不得自动推进到 `import` approval-pending；应返回确定性 skip 文本，并保留手动 `import <id/hash>` 路径
  - skip truth 继续复用现有 `job_event`，记录为 `auto_import.skipped_by_rule`，避免后续 `status` 重复自动推进或重复 skip 提示
  - 当前 next smallest path 前进到 filename normalization / rename baseline
- **原因**：
  先用最小确定性规则补齐自动化闭环第二步，优先过滤明显低质量资源，同时不把仓库提前扩成完整资源评分平台。
- **验证**：
  已通过 targeted pytest、全量 pytest、临时 `tmp_tests` 手工脚本验收（脚本已按规范清理）。

## D-043 filename normalization / rename 最小基线已并入主线
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - confirmed import 在现有导入路径上已接入最小 deterministic 文件名规范化
  - 目标命名优先使用已持久化的 downloader 成功标题真相（`downloader.succeeded`），缺失时回退到 Transmission 导入源名称
  - 命名规则在 hardlink 与 copy-fallback 二次 `confirm` 路径保持一致
  - 既有 Telegram 命令词、approval 边界、`jobs` 所有权、lease/version、防重放协议保持不变
  - 当前 next smallest path 前进到 metadata scraping (`TMDB + Fanart.tv`) baseline
- **原因**：
  先用最小改动补齐入库后命名规范化缺口，同时保持既有副作用安全边界和控制层协议稳定。
- **验证**：
  已通过 targeted pytest、全量 pytest、临时 `tmp_tests` 手工脚本验收（脚本已按规范清理）。

## D-044 metadata scraping (`TMDB + Fanart.tv`) 最小基线已并入主线
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - confirmed import success 现在在现有导入成功路径上确定性触发 metadata scraping
  - metadata scrape 输入优先使用已持久化 downloader 成功标题真相（`downloader.succeeded`），缺失时回退到规范化导入目标命名
  - 当 `TMDB_API_KEY` 可用但 `FANART_API_KEY` 缺失时，仍写入 TMDB metadata，fanart 图片字段为空
  - metadata scrape 失败必须显式记录为 `metadata.failed`，并打印可读错误/建议；失败不回滚 confirmed import 成功
  - 既有 Telegram 命令词、approval 边界、`jobs` 所有权、lease/version、防重放协议保持不变
  - 当前 next smallest path 前进到 subtitle auto-translation baseline
- **原因**：
  先用最小改动补齐“导入后 metadata 侧车文件”这一自动化闭环缺口，同时保持现有副作用安全边界和控制层协议稳定。
- **验证**：
  已通过 targeted pytest、全量 pytest、临时 `tmp_tests` 手工脚本验收（脚本已按规范清理）。

## D-045 subtitle auto-translation 最小基线已并入主线
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - confirmed import success 现在在现有导入成功路径上确定性触发 subtitle auto-translation
  - 仅处理 SubRip (`.srt`) 字幕；输出 `*.zh.srt`，并保持原始序号与时间轴结构
  - 默认翻译路径改为专业模型逐行翻译（OpenAI-compatible `chat/completions`），默认模型 `gpt-5.4`
  - 缺少 `SUBTITLE_TRANSLATION_API_KEY` 或模型调用失败时，必须显式记录 `subtitle.failed` 并打印可读错误/建议；失败不回滚 confirmed import success
  - 既有 Telegram 命令词、approval 边界、`jobs` 所有权、lease/version、防重放协议保持不变
  - 当前 next smallest path 前进到 series / anime watchlist-driven tracking baseline
- **原因**：
  先用最小改动补齐“导入后字幕自动翻译”闭环缺口，并把默认路径提升到专业翻译模型，避免低质量规则替换误导用户。
- **验证**：
  已通过 targeted pytest、全量 pytest、临时 `tmp_tests` 手工脚本验收（脚本已按规范清理）。

## D-046 对 OpenHarness 的借鉴边界：只吸收机制，不改项目定位
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - OpenHarness 只作为“通用 agent harness 怎么搭”的外部参考，不改变 Luminarr 的垂直媒体自动化定位
  - 当前明确可借鉴的机制只有：
    - 后台任务生命周期（例如 created -> running -> completed/failed/cancelled），供后续 scheduler / tracking 真相层参考
    - `PreToolUse / PostToolUse` 一类统一 hook 点，供后续 audit log / 通知 / 恢复逻辑复用
    - path-level 权限规则，供后续硬链接 / copy / 刮削图片 / 字幕写回这类文件动作做显式 allow/deny
    - 多 agent / coordinator 思路，仅作为更后面的 scheduler 协调参考
  - 当前明确不引入：
    - 通用 40+ 工具平台
    - React TUI
    - plugin / skill / MCP 平台化
    - 为了“更像通用 harness”而重写现有垂直工作流
- **原因**：
  Luminarr 解决的是“影视自动化流水线稳定跑通”问题，不是“做一个通用 agent 底座”。只吸收能提升边界清晰度和可恢复性的机制，避免仓库被带成另一个方向。

## D-047 阶段 C 的 PT / BT 主干必须在 parser 层先分叉
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 后续进入 BT/PT 分流时，分叉点必须在 parser / 意图识别层，而不是到了下载后半段再临时判断
  - **PT 主干**只承接正常观影需求，例如：
    - `我想看 X`
    - `追更 X`
    - `watchlist` / `想看`
  - PT 主干继续走现有观影链路：TMDB -> Prowlarr PT 源 -> 资源选择 -> PT 下载器角色 -> 导入 / 规范化命名 / 刮削 / 字幕 / Emby
  - **BT 主干**只承接直接 BT 下载需求，例如：
    - 用户直接发 `magnet:?xt=...`
    - 用户明确说“下载这个 BT / 下载这个磁力”
  - 当系统收到磁力或明确 BT 下载指令时，必须先补一次最小分类询问：电影 / 电视剧 / 动漫 / 其他 BT 资源
  - BT 主干与 PT 主干从入口开始天然隔离，不共享“正常观影需求”的搜索与自动化判断
  - 该决策只定义后续阶段 C 的边界；不改变当前主线仍然是 Transmission-only、movie-first 的事实
- **原因**：
  PT 是本项目电影/剧集/动漫观影需求的主渠道；直接 BT/磁力是另一类下载需求。先在入口分流，后面代码才不会把两类目标搅在一起。

## D-048 多下载器采用“角色绑定”，不把 PT / BT 写死到某个软件
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 后续多下载器支持采用“下载器实例 + 角色绑定”模型：
    - 配置中先定义具体下载器实例
    - 再把 `pt_downloader`、`bt_downloader` 这两个角色绑定到具体实例
  - `pt_downloader` 与 `bt_downloader` 可以绑到同一个实例，也可以绑到不同实例
  - 代码层只认“PT 角色 / BT 角色”，不硬编码“PT 一定是 Transmission”或“BT 一定是 qBittorrent”
  - 当前已实现客户端仍然只有 Transmission；`qBittorrent` 仍是后续 BT 阶段的候选客户端，不是当前主线事实
  - 后续 BT 主干默认只做“下载 -> 转移/放置文件”这条最小链路，不自动进入 PT 主干里的 metadata scrape / subtitle auto-translation
- **原因**：
  这样后续加新下载器时，不需要重写整条业务链；同时也能保住“BT 资源天然隔离”的边界，不把 PT 自动化链硬套到 BT 资源上。

## D-049 BT 分类后的后半段：媒体型 BT 走 TMDB/刮削/字幕，原始 BT 走规则化转移
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 当用户发送磁力或明确要求直接下载 BT 资源时，系统先进入 BT 主干，再补一次最小分类询问：
    - 电影
    - 电视剧
    - 动漫
    - 其他 BT 资源
  - 当用户选择电影 / 电视剧 / 动漫时，该任务属于“媒体型 BT”：
    - 系统必须尝试做 TMDB 关联，并把 `media_kind` 与 `tmdb_id` 记入持久化真相
    - 如果 TMDB 返回多个合理候选，必须继续让用户确认
    - 如果 TMDB 无法可靠关联，必须显式提示用户补标题或改选“其他 BT 资源”，不得静默跳过
    - 下载完成后，继续复用现有媒体后半段链路：规范化命名、metadata scrape、海报/图片侧车、subtitle auto-translation、媒体库 refresh
  - 当用户选择“其他 BT 资源”时，该任务属于“原始 BT”：
    - 不做 TMDB 关联
    - 不做 metadata scrape / 海报 / subtitle auto-translation / 媒体库 refresh
    - 系统只提供预先配置好的目标目录选项（例如 A 目录 / B 目录），并在投递问询阶段交由用户选择
    - 任务真相中必须持久化记住用户选择的目标目录别名
    - 下载完成后只做文件转移 / 放置到该已选目录
    - 不做文件内容级自动分类，不依赖 AI 临时猜测目录
  - D-048 中“BT 主干默认不进入 metadata / subtitle 链”的旧表述，仅继续适用于“其他 BT 资源”，不再适用于电影 / 电视剧 / 动漫类 BT
- **原因**：
  电影、剧集、动漫类磁力本质上还是媒体资源，应该尽量复用已经落地的入库后半段；只有真正的原始 BT 文件才保持纯转移路径。

## D-050 下载器实例模型：支持多个 Transmission / qBittorrent 实例，PT/BT 只绑定角色
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 系统后续支持两类下载器协议：
    - Transmission
    - qBittorrent
  - 配置层先声明“下载器实例列表”，每个实例至少要有：
    - 实例名
    - 类型（Transmission / qBittorrent）
    - 地址 / 认证信息
    - 该实例对应的下载目录真相
  - 同一种类型允许存在多个实例，例如多个 Transmission、多个 qBittorrent
  - `pt_downloader` 与 `bt_downloader` 只绑定到“实例名”，不直接绑定到某个软件类型
  - `pt_downloader` 与 `bt_downloader` 可以：
    - 指向同一个实例
    - 指向不同实例
    - 指向同类型的不同实例
    - 指向不同类型的实例
  - 任务真相中后续必须持久化记录：
    - 当前任务属于 PT 还是 BT
    - 当前任务属于 movie / series / anime / raw_bt 哪一类
    - 当前任务实际投递到了哪个下载器实例
    - 该实例属于哪种协议
  - 当前已经实现的客户端仍然只有 Transmission；qBittorrent 只是后续要接入的协议，不是当前已落地事实
- **原因**：
  下载器是外部依赖，真实环境里经常会有多个实例。先把“实例”和“角色”分开，后面加新实例、新协议或改路由时，业务链才不会被迫重写。

## D-051 series / anime watchlist-driven tracking 最小基线已并入主线
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - `watchlist_item` 持久化真相已最小扩展为：
    - `title`
    - `year`
    - `media_kind`（`movie` / `series` / `anime`）
  - 旧 SQLite `watchlist_item` 数据在初始化升级时，必须确定性补成 `media_kind='movie'`
  - 现有手动 `watchlist` 命令保持成立，并补充最小显式分类写法：
    - `watchlist add <片名 [年份]>` 继续默认按 `movie`
    - `watchlist add <movie|series|anime> <片名 [年份]>`
  - `watchlist list` 现在必须显式展示条目类型，便于用户按 `movie / series / anime` 区分同名条目
  - 同一 chat 下，同标题同年份但不同 `media_kind` 的 watchlist 条目允许并存
  - 该步仍然严格保持手动基线：
    - 不触发 downloader side effects
    - 不触发 import side effects
    - 不引入 scheduler
    - 不引入 tracking rule engine
  - 当前 next smallest path 前进到 PT / BT parser-level intent split baseline
- **原因**：
  先把“想看条目到底是电影、剧集还是动漫”记成持久化真相，再进入后续 PT/BT 分流与更深的内容类型工作，避免后面流程继续建立在模糊条目上。
- **验证**：
  已通过 focused pytest（watchlist 相关）与临时 `tmp_tests` 手工脚本验收（脚本已按规范清理）。

## D-052 PT / BT parser-level intent split 最小基线已并入主线
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 现有 Telegram parser / routing 入口现在已按最小可用形状接入 PT / BT 分流
  - 正常观影需求继续走现有 PT 主干：搜索 / 选择 / 下载审批 / 状态 / 导入 / refresh / watchlist
  - 直接 BT / 磁力需求在入口层被确定性拦出，不再误入普通电影搜索路径
  - 当前最小识别范围只包括：
    - 原始 `magnet:?` 链接
    - 明确 `下载这个 BT / 下载这个磁力` 一类文本
  - 当前这一步严格保持 parser/routing-only：
    - 不创建新持久化协议
    - 不发起 downloader side effects
    - 不接入 BT 分类后半段
    - 不引入 downloader-role binding
  - 现有 `search/select/status/import/confirm/watchlist` 命令词、approval 边界、`jobs` 所有权、lease/version、防重放、callback 路由保持不变
  - 当前 next smallest path 前进到 BT classification follow-up baseline
- **原因**：
  先把“正常观影需求”和“直接 BT 下载需求”在入口层硬分开，后面再补 BT 分类和后半段时，代码边界才不会继续混在一起。
- **验证**：
  已通过 focused pytest（`tests/test_telegram_bot.py`）与临时 `tmp_tests` 手工脚本验收（脚本已按规范清理）。

---

## 附：更新模板

### D-XXX 标题
- **状态**：已决定 / 已废弃 / 已替换
- **日期**：YYYY-MM-DD
- **结论**：
- **原因**：
- **影响范围**：
- **替代项**：（如有）
