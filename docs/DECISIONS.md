# docs/DECISIONS.md (v20)

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

---

## 附：更新模板

### D-XXX 标题
- **状态**：已决定 / 已废弃 / 已替换
- **日期**：YYYY-MM-DD
- **结论**：
- **原因**：
- **影响范围**：
- **替代项**：（如有）
