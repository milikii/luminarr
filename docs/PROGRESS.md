## Round 0 — 2026-04-28 00:00

### 完成
- 项目初始化

### 测试状态
- 通过: 0 / 总计: 0

### 遗留 / 下轮继续
- 等待按执行计划进入成人 BT minimum wedge

### 下轮目标
- 修复 docs gate 并开始 Task 1

## Round 1 — 2026-04-28 19:56

### 完成
- 补齐 `docs/PROGRESS.md`、`docs/BLOCKERS.md` 和 `.worktrees/` 忽略规则，解除执行前置阻断
- 归档 `docs/DEPLOY_CHECKLIST.md` 与 `docs/BT_SCORING_RULES.md`
- 调整 docs gate，将 `PROGRESS.md` / `BLOCKERS.md` 排除出 active docs 预算，并更新 `docs/GETTING_STARTED.md`

### 测试状态
- 通过: 35 / 总计: 35

### 遗留 / 下轮继续
- 继续执行成人 BT minimum wedge Task 2

### 下轮目标
- 增加 `成人搜` 只读查询别名并补齐成人只读回复详情链接

## Round 2 — 2026-04-28 20:01

### 完成
- 为 BT 只读查询增加 `成人搜` 显式入口别名
- 在成人只读探索和批量预览回复中展示 javlibrary 详情链接
- 更新只读说明文案，明确成人下载链应通过发送磁力并选择 `BT 成人链`

### 测试状态
- 通过: 18 / 总计: 18

### 遗留 / 下轮继续
- 继续执行成人 BT minimum wedge Task 3

### 下轮目标
- 让成人历史信息进入待下载回复

## Round 3 — 2026-04-28 20:08

### 完成
- 为 `AddPendingContextBuilder` 增加基于 `adult_content_registry` 的成人历史回填
- 让 direct magnet 待下载回复沿用成人历史文案
- 对不支持历史查询的轻量假 repo 保持 fail-open，不影响待下载创建

### 测试状态
- 通过: 10 / 总计: 10

### 遗留 / 下轮继续
- 继续执行成人 BT minimum wedge Task 4

### 下轮目标
- 增加成人 BT focused 验证入口并跑总 gate

## Round 4 — 2026-04-28 20:14

### 完成
- 新增 `make verify-adult-bt-wedge` 与对应 Makefile 测试
- 在 `docs/GETTING_STARTED.md` 增加成人 BT focused 验证入口
- 修复 `handle_confirm_query()` 对 confirm job lookup `RuntimeError` 未 fail-closed 的回归，确保新 focused target 通过
- 通过 `make verify-adult-bt-wedge`、`make quality`、`make verify-mainline`

### 测试状态
- 通过: 3 / 总计: 3

### 遗留 / 下轮继续
- 无

### 下轮目标
- 等待用户指令

## Round 5 — 2026-04-28 20:49

### 完成
- 启动本地 `app.main`，开启 Telegram 人工 smoke 前置运行环境
- 将 `AGENTS.md`、`STATUS.md`、`NEXT_STEP.md`、`TASKS.md` 切到 “adult BT 已完成 / 下一条主线为 config 启动硬依赖解耦” 的当前真相
- 同步执行计划尾部的最终验证状态与 active docs 预算统计口径

### 测试状态
- 待本轮文档收口后重跑 docs / quality gate

### 遗留 / 下轮继续
- 等待 Telegram 人工 smoke 结果

### 下轮目标
- 开始 `app/config.py` 启动硬依赖解耦

## Round 6 — 2026-04-29 00:44

### 完成
- 定稿 `docs/plans/2026-04-29-config-startup-dependency-decoupling.md`
- 锁定 config 主线方案 A：本轮只解耦 `PROWLARR_*` 与 legacy `TRANSMISSION_BASE_URL`；`TELEGRAM_BOT_TOKEN` 继续保持当前宿主必填
- 同步更新 `docs/STATUS.md`、`docs/NEXT_STEP.md`、`docs/TASKS.md`，让当前主线真相与计划一致

### 测试状态
- 通过: 3 / 总计: 3

### 遗留 / 下轮继续
- 按定稿计划进入 `app/config.py` capability contract 实施

### 下轮目标
- 先补 capability matrix 和 focused tests，再收口 config 校验与启动装配

## Round 7 — 2026-04-29 01:38

### 完成
- 完成 `app/config.py` 启动硬依赖解耦方案 A：`PROWLARR_*` 改为能力必填，legacy `TRANSMISSION_BASE_URL` 改为在已有可用 downloader instances 时可选
- 同步收口 `app/main.py` 装配、搜索 / `btsub run` unavailable guard、legacy downloader fallback fail-closed 语义
- 补齐 focused tests、`.env.example` 与 `docs/GETTING_STARTED.md` 能力边界说明
- 通过 reviewer 反馈闭环，确认 `bt搜` / `bt批量` 不被误伤，`btsub list/add/remove/clear` 在降级标记存在时仍可用

### 测试状态
- 通过: 3 / 总计: 3

### 遗留 / 下轮继续
- 进入 `telegram_sidecar_runtime.py` 宿主解耦主线

### 下轮目标
- 先盘点 Telegram `Application` 生命周期下当前承载的 sidecar 与 scheduler，再拆出非 Telegram 运行所需的宿主边界

## Round 8 — 2026-04-29 01:56

### 完成
- 完成 `telegram_sidecar_runtime.py` 宿主解耦：抽出通用 sidecar host 边界，Telegram 生命周期只保留 wrapper/委托
- 让 Feishu、WeCom、personal WeChat、下载完成轮询、post-download auto-import 与 `btsub` scheduler 通过通用 host 生命周期启动/停止
- 让 `btsub` scheduler 通知发送改走宿主注入的 `send_text` callback，而不是硬绑 `Application.bot.send_message`
- 补齐 sidecar focused tests，并通过总回归

### 测试状态
- 通过: 3 / 总计: 3

### 遗留 / 下轮继续
- 进入超大业务文件收口主线

### 下轮目标
- 先盘点 `add_to_downloader.py`、`import_to_library.py`、`manage_bt_subscription.py`、`search_media.py`、`cleanup_downloaded_source.py`、`subtitle_translation_support.py` 的体量与单消费者切口，再决定最小拆分顺序

## Round 9 — 2026-04-29 08:35

### 完成
- 将 `manage_bt_subscription.py` 的候选选择 / 打分解析 helper 下沉到 `bt_subscription_candidate_helpers.py`
- 新增 `bt_candidate_metadata.py` 作为公开 BT candidate metadata 解析边界，并让 `pure_bt` 与 `manage_bt_subscription` 复用同一套实现
- 为首个超大业务文件收口切口补齐 focused tests，并通过 spec/quality 两层复审

### 测试状态
- 通过: 3 / 总计: 3

### 遗留 / 下轮继续
- 进入 Feishu 可选依赖策略主线

### 下轮目标
- 盘点 `lark_oapi` 的真实运行边界和安装入口，收口 requirements / extras / operator docs 其中一个最小方案

## Round 10 — 2026-04-29 08:53

### 完成
- 在 `requirements.txt` 明确补入 `lark-oapi==1.5.3`
- 收口 `docs/GETTING_STARTED.md` 的 Feishu 安装真相：标准 requirements 已包含 SDK，运行时是否启用仍由 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 决定
- 新增 `tests/test_feishu_dependency_contract.py`，保护 requirements 与 operator docs 口径一致

### 测试状态
- 通过: 2 / 总计: 2

### 遗留 / 下轮继续
- 进入依赖告警清理主线

### 下轮目标
- 收口 `lark_oapi` / `websockets` deprecation warnings，优先找出可通过升级或局部隔离解决的最小切口

## Round 11 — 2026-04-29 09:04

### 完成
- 在 `feishu_long_connection.py` 局部隔离 `lark_oapi` / `websockets` 已知 deprecation warnings
- 新增 `tests/test_feishu_dependency_contract.py` 与 `tests/test_feishu_long_connection.py` 的 focused contract/导入期保护
- 通过 fresh `make quality`、`make verify-mainline`，并确认主线输出里已不再出现那 4 条已知 deprecation warnings

### 测试状态
- 通过: 2 / 总计: 2

### 遗留 / 下轮继续
- 进入 non-Telegram 一等公民主线

### 下轮目标
- 评估非 Telegram 运行模式要成为一等公民时，还缺哪些入口/部署/通知/宿主真相

## Round 12 — 2026-04-29 09:12

### 完成
- 确认 Task 6 “把 non-Telegram 运行模式做成一等公民” 已超出单文件或单职责收口范围
- 按执行纪律将该阻断写入 `docs/BLOCKERS.md`

### 测试状态
- 通过: 0 / 总计: 0

### 遗留 / 下轮继续
- 等待把 Task 6 收口成一个明确的 non-Telegram 最小运行画像

### 下轮目标
- 锁定首个 non-Telegram 一等公民画像与 focused tests 边界

## Round 13 — 2026-04-29 09:40

### 完成
- 锁定首个 non-Telegram 一等公民最小画像为 `Feishu-only` 文本私聊独立启动 + 当前入站即时回复
- 让 `TELEGRAM_BOT_TOKEN` 改为 Telegram 宿主条件必填，并新增非 Telegram host 启动路径
- 让无主动 `send_text` 能力的宿主显式跳过 `btsub` 后台扫描，避免把 non-Telegram 后台通知伪装成可用

### 测试状态
- 通过: 6 / 总计: 6

### 遗留 / 下轮继续
- `WeCom-only` 独立宿主与 non-Telegram 后台主动通知可逆会话真相仍未完成

## Round 14 — 2026-04-29 11:03

### 完成
- 新增 `app/bot/channel_contact_runtime.py`，实现 in-memory channel contact registry 与可逆查询 API
- 在 Feishu / WeCom / personal WeChat 入站路径里记录外部会话地址到 `bot_data`
- 给 `main` 与 Telegram build path 注入同一个联系人注册表实例，保持 Feishu-only / WeCom-only 独立宿主不回退
- 补齐 focused tests，覆盖 registry fail-closed、入站记录回查和 main 注入

### 测试状态
- 通过: 8 / 总计: 8

### 遗留 / 下轮继续
- non-Telegram 后台主动通知仍只完成了可逆真相层，尚未接入真正回发实现

### 下轮目标
- 把联系人注册表接到后台通知发送链路，再单独处理 personal WeChat 登录重做或 richer reply

## Round 14 — 2026-04-29 10:35

### 完成
- 落地 `WeCom-only` 独立宿主：Telegram token 为空时，若 WeCom 三元组完整，则会走 webhook + shared runtime 的 non-Telegram 启动路径
- 保持 `Feishu-only` 最小画像不回退，并让 non-Telegram 启动选择在 WeCom 与 Feishu 之间有明确优先级
- 保持无主动 `send_text` 能力的宿主显式不启动 `btsub` 后台扫描，避免伪装成可用

### 测试状态
- 通过: 12 / 总计: 12

### 遗留 / 下轮继续
- non-Telegram 后台主动通知所需的可逆会话真相仍未完成

### 下轮目标
- 把后台通知的“内部 `chat_id` 到可发回路”单独收口成下一层真相

## Round 15 — 2026-04-29 11:05

### 完成
- 新增 non-Telegram 运行态联系人注册表，按内部 `chat_id` 记录 Feishu / WeCom / personal WeChat 的外部会话地址
- 让 Feishu / WeCom / personal WeChat inbound 在进入 shared runtime 前写入可逆会话真相
- 保持当前不改 SQLite schema，只补 truth layer，不把后台主动发送实现偷带进来

### 测试状态
- 通过: 16 / 总计: 16

### 遗留 / 下轮继续
- non-Telegram 后台主动通知仍未真正接上可发回路

### 下轮目标
- 把运行态联系人注册表接到后台回发链路，定义 Feishu / WeCom 的最小发送协议与失败语义

## Round 16 — 2026-04-29 13:22

### 完成
- 新增显式 `watchlist sync` / `想看 同步`，把想看清单按相同 `chat_id` / `title` / `year` / `media_kind` 桥接到 `btsub`
- 给 `BtSubscriptionRepo` 补单事务批量写入，确保 bridge 失败时不会残留部分成功
- 补齐 watchlist bridge、main wiring、BT subscription repo 原子写入的 focused tests

### 测试状态
- 通过: 7 / 总计: 7

### 遗留 / 下轮继续
- `BT subscription` 扩边主线仍未开始；本轮只完成了 `watchlist -> btsub` 桥接

### 下轮目标
- 锁定 `BT subscription` 下一条最小扩边切口，优先 raw BT subscription contract，同时继续保持人工 `confirm` 边界

## Round 17 — 2026-04-29 13:34

### 完成
- 纠正 `STATUS.md` / `NEXT_STEP.md` / `TASKS.md` 的主线漂移，重新锁定 BT 支线只承接成人资源
- 明确写回 direct `BT` / `magnet:?` 入口继续保留 `观影 PT 链 / BT 成人链` 问询，不绕过链路选择

### 测试状态
- 待本轮文档口径修正后重跑 docs / quality gate

### 遗留 / 下轮继续
- 成人 BT 专线后续若继续扩边，仍需先定义最小可复验 contract

### 下轮目标
- 在不引入影视资源 BT 订阅的前提下，决定成人 BT 专线是否还需要新的连续追踪能力

## Round 18 — 2026-04-29 13:45

### 完成
- 继续梳理活跃文档入口，补齐 `README.md` 与 `docs/HUMAN_START_HERE.md` 的 BT 专线边界说明
- 明确写回：BT 只承接成人资源；direct `BT` / `magnet:?` 仍先问 `观影 PT 链 / BT 成人链`

### 测试状态
- 待本轮入口文档收口后重跑 docs / quality gate

### 遗留 / 下轮继续
- 若还有历史活跃文档继续误导“BT 可继续扩成通用影视线”，继续清理

### 下轮目标
- 完成活跃文档一致性检查，并确认后续计划入口不再漂移

## Round 19 — 2026-04-29 15:10

### 完成
- 将 `btsub add` 从通用 `movie / series / anime` 收口成成人 BT 精确番号追踪
- 让旧的非成人 `btsub` 条目在 `run` / scheduler 路径上显式告警并跳过扫描
- 将 `watchlist sync` 改为 fail-closed，明确想看清单继续只服务 PT 主线

### 测试状态
- 通过: 3 / 总计: 3

### 遗留 / 下轮继续
- 成人 BT 专线若继续扩连续追踪能力，仍要先定义最小 contract，不放宽 direct BT 问询与 `confirm` 边界

### 下轮目标
- 决定成人 BT 专线是否需要更进一步的连续追踪体验，但不回切影视 BT 或 raw BT 订阅

## Round 20 — 2026-04-29 16:56

### 完成
- 为 `btsub` 连续追踪补齐最小去重 contract：同标题但不同 URL 的镜像命中不再重复创建下载待确认
- 让 `btsub run` 与 scheduler 复用同一套 same-title 去重判定，避免两个入口行为漂移
- 将 `btsub list` 文案明确为“上次命中资源”，让当前追踪状态对操作者更直观

### 测试状态
- 通过: 5 / 总计: 5

### 遗留 / 下轮继续
- 若还要继续扩成人 BT 连续追踪，只能在当前 adult-only / manual-confirm 边界内先定义新的最小 contract

### 下轮目标
- 如继续推进 BT subscription，只讨论更进一步的成人 BT 连续追踪 contract，不回切影视 BT、raw BT 或 auto-confirm

## Round 21 — 2026-04-30 00:35

### 完成
- 补齐 Telegram 成人 BT 真机 smoke 证据，并把 `docs/STATUS.md` / `docs/NEXT_STEP.md` 从“待验证”切到完成态
- 把运行时外部依赖真相页统一收口到 `docs/GETTING_STARTED.md`，让 `README.md`、`docs/OPERATOR_RUNBOOK.md`、`docs/STATUS.md` 改成引用式入口
- 将 `search_media.py` 的候选/澄清状态持久化 helper 抽到 `app/services/search_media_state.py`，并补齐 focused tests 保护重启恢复与 fail-closed 语义
- 将 `docs/TASKS.md` 的 `T13`、`T14`、`T15` 全部打勾，当前任务清单清空

### 测试状态
- 通过: 6 / 总计: 6

### 遗留 / 下轮继续
- 无；当前执行清单已完成，默认进入冻结态

### 下轮目标
- 若用户继续推进，先做冷启动一致性检查，再决定是否开启新主线

## Round 22 — 2026-04-30 09:31

### 完成
- 执行完成态冻结的冷启动一致性检查，确认 `make quality`、`make verify-mainline`、`make verify-adult-bt-wedge`、`make lint` 全部通过
- 复核 `docs/TASKS.md` 仍无未完成项，继续保持当前 adult-only BT 边界、shared runtime 边界和运行依赖真相页冻结

### 测试状态
- 通过: 4 / 总计: 4

### 遗留 / 下轮继续
- 无；除非出现新的失败证据或新的明确需求，否则继续保持完成态冻结

### 下轮目标
- 若用户开启新主线，先更新 `docs/NEXT_STEP.md` 与 `docs/TASKS.md`，再进入新的执行循环

## Round 23 — 2026-04-30 11:02

### 完成
- 用 `context-restore` 恢复上次 Stage 1 设计上下文，确认当前仓库“没有任务”只是因为 `docs/TASKS.md` 仍停在完成态冻结
- 新增 `docs/plans/2026-04-30-adult-duplicate-memory-execution.md`，把 Stage 1 的首个可执行切口锁成 `T16 成人 BT 下载前防重记忆层`
- 更新 `docs/NEXT_STEP.md`、`docs/STATUS.md`、`docs/TASKS.md`，将当前唯一执行入口从冻结态切换到 `T16`

### 测试状态
- 待本轮文档收口后重跑 quality / mainline / adult-bt / lint gate

### 遗留 / 下轮继续
- `T16` 尚未实现；`T17 Telegram-first 高频主链交付层` 和 `T18 成人 BT 来源角色底座` 仍停留在任务排队阶段

### 下轮目标
- 按 `docs/plans/2026-04-30-adult-duplicate-memory-execution.md` 进入 `T16` 实施，并在实现完成后重跑全部 gate

## Round 24 — 2026-04-30 12:20

### 完成
- 完成 `T16 成人 BT 下载前防重记忆层`：新增 `adult_duplicate_memory_snapshot` sibling 真相、`AdultDuplicateMemoryService`、`AddToDownloaderService` duplicate gate、`duplicate_override` follow-up 和 operator tooling
- 在 `main.py` 完成 duplicate memory wiring，让运行时真实装配 `AdultDuplicateMemoryService` 和 `BtPendingRepo`
- focused verification 全绿：snapshot persistence、duplicate service/tooling、duplicate gate/runtime、main wiring 均已通过
- 将 `docs/NEXT_STEP.md`、`docs/STATUS.md`、`docs/TASKS.md` 切到 `T17 Telegram-first 高频主链交付层`

### 测试状态
- 通过: 4 / 总计: 4

### 遗留 / 下轮继续
- `T17 Telegram-first 高频主链交付层` 尚未开始；需要在不回退 duplicate 语义的前提下收口 Telegram 高频主链交付体验

### 下轮目标
- 进入 `T17 Telegram-first 高频主链交付层`，优先搜索结果、下载确认、状态反馈和关键 BT follow-up 的 Telegram-first 交付

## Round 25 — 2026-04-30 13:28

### 完成
- 完成 `T17 Telegram-first 高频主链交付层`：补齐 Telegram inline actions 基础设施，收口 duplicate warning 主体验、关键 BT follow-up 提示交付和导入审批 Telegram-first 文本结构
- 保持 shared runtime 业务语义不变，所有按钮继续回译到既有文本 query，不新增业务协议
- 通过 focused verification 与仓库级 gate，确认 `T17` 没有带偏 adult-only BT 边界或 docs gate

### 测试状态
- 通过: 4 / 总计: 4

### 遗留 / 下轮继续
- `T18 成人 BT 来源角色底座` 尚未开始；需要固定主力 BT / 辅助 PT / helper-only 角色，避免后续扩站继续漂移

### 下轮目标
- 进入 `T18 成人 BT 来源角色底座`，先锁定来源角色真相与 helper-only 边界

## Round 26 — 2026-04-30 14:56

### 完成
- 完成 `T18 成人 BT 来源角色底座`：在 `app/services/bt_sources.py` 收口来源角色真相与别名归一化，引入 `primary / supporting / helper_only` 角色，并为 BT candidate 增加 `btSourceName` / `btSourceRole`
- 让 `app/main.py` 通过 `get_configured_web_source_rule()` 只装配允许主动搜索的来源，保持 `javlibrary` helper-only，不再进入主动下载来源
- 让 `app/services/bt_read_only_display.py` 复用 `bt_sources` 的角色/优先级真相，移除散落的来源优先级与别名表
- 补齐 focused tests，并新增 `.trellis/spec/backend/bt-source-contracts.md` 记录来源角色、环境装配和 candidate payload 契约

### 测试状态
- 通过: 4 / 总计: 4

### 遗留 / 下轮继续
- `T19 Stage 1 聚合验证与运维真相同步` 尚未开始；仍需补新的 focused verification 入口、实机 smoke/等价证据和 operator-facing 文档同步

### 下轮目标
- 进入 `T19 Stage 1 聚合验证与运维真相同步`，补验证矩阵并同步当前实现真相

## Round 27 — 2026-04-30 20:32

### 完成
- 完成 `T19 Stage 1 聚合验证与运维真相同步`：新增 `make verify-stage1` 及其 `duplicate-memory` / `telegram-delivery` / `bt-source-roles` 三个子入口，固定为 Stage 1 单一 focused verification 真相
- 同步 `docs/GETTING_STARTED.md`、`docs/STATUS.md`、`docs/NEXT_STEP.md`、`docs/OPERATOR_RUNBOOK.md` 和 docs gate 测试，让 operator-facing 文档与当前实现、收尾阶段口径和 `verify-stage1` 保持一致
- 在无法新增真实 Telegram 入站 smoke 的环境下，明确记录 `telegram bot api unreachable`、`no luminarr process running` 快照，并保留 `logs/trace.log` 中既有真实 Telegram 链路作为等价证据
- 将 `T19` 标记完成，并把 `.trellis/spec/backend/quality-guidelines.md` 补齐为 Stage 1 verification entrypoint 契约

### 测试状态
- 通过: 5 / 总计: 5

### 遗留 / 下轮继续
- 进入收尾阶段；若要补新的真实 Telegram smoke，需先恢复 `api.telegram.org` 可达性并启动本地 `app.main`

### 下轮目标
- 按收尾阶段执行 commit / archive / journal 收口，或进入 QA / ship

## Round 28 — 2026-04-30 22:58

### 完成
- 完成 `成人搜` adult-only fallback：`成人搜` 继续走当前 BT 只读入口，但当只读候选为空时，会仅基于当前已配置的 adult-only 来源做同源 fallback，不再直接停在通用只读空结果
- 保持边界不回退：fallback 不进入 PT 主链搜索、不扩到未配置成人源；当当前 adult-only 来源确实为空时，明确回复“当前已配置成人源无结果”
- 同步补齐 `tests/test_search_media.py` 和 `tests/test_private_chat_bt_read_only_runtime.py` focused coverage，保护 adult-only fallback、有结果/无结果和运行时 `成人搜` 路由透传

### 测试状态
- 通过: 2 / 总计: 2

### 遗留 / 下轮继续
- 若要继续收尾，需要对本轮 adult-search-fallback 变更做 commit，并在之后继续 QA / ship

### 下轮目标
- 提交 `adult-search-fallback` 变更并继续 Telegram 路径 QA

## Round 29 — 2026-05-01 07:35

### 完成
- 完成 `Telegram 结果交互与成人 metadata 主辅源重排` 第一阶段：成人搜索结果改为 Telegram 分层布局，保留裸 `magnet:?` 便于点击 / 复制，并补上海报、标准信息、制作信息、详情链接和 Metadata 来源角色展示
- 固定成人 metadata source policy：`avmoo / avbase / jav321 / avsox / caribbeancom / missav` 作为默认主候选，`javlibrary` 降为 `backup_cross_check`，`javbus` 降为 supporting / 非默认主源，`fanza` 作为条件增强源
- 扩展 JavLibrary backup helper 的只读解析字段，并把新契约写入 `.trellis/spec/backend/bt-source-contracts.md`
- 归档 Trellis task `05-01-telegram-adult-result-ux-and-metadata`，session journal 已写入本地 `.trellis/workspace/alex/journal-1.md`

### 测试状态
- 通过: 5 / 总计: 5

### 遗留 / 下轮继续
- 这一轮只完成交互壳、source policy 和 JavLibrary backup metadata 解析；尚未接入 `avmoo / avbase / jav321 / avsox / caribbeancom / missav` 的真实 helper client
- Telegram 客户端对裸 `magnet:?` 的点击行为取决于客户端实现；当前输出已保留完整裸链接，至少可复制

### 下轮目标
- 若继续优化成人 metadata，优先选 1 个主 metadata helper 做真实接入和 Telegram 实机 smoke；若准备发布，先进入 QA / ship

## Round 30 — 2026-05-01 09:07

### 完成
- 完成 `Avmoo adult metadata helper` 第一阶段：新增 Avmoo 静态 HTML 只读 helper，并在运行时先查 Avmoo、失败或空结果后回退 JavLibrary
- 保持边界不变：未引入无头浏览器、新依赖、PT fallback、下载器来源或自动副作用
- 用真实 Avmoo HTML fixture 验证 `SSIS-483` 的海报、发行日、时长、导演、制作商、发行商、系列、类别和演员字段均可解析
- 更新 `.trellis/spec/backend/bt-source-contracts.md`，记录 Avmoo primary + JavLibrary backup 的 helper chain 契约
- 归档 Trellis task `05-01-avmoo-adult-metadata-helper`，session journal 已写入本地 `.trellis/workspace/alex/journal-1.md`

### 测试状态
- 通过: 4 / 总计: 4

### 遗留 / 下轮继续
- live Avmoo Python helper smoke 在当前沙箱网络路径下没有稳定返回；当前以 curl 抓取页和保存的真实 HTML fixture 解析作为等价证据
- Avmoo HTML 不是正式 API，后续若页面结构漂移会 fail-closed 并回退 JavLibrary

### 下轮目标
- 若继续增强成人 metadata，优先做真实 Telegram smoke 或接第二个主 helper；若准备发布，进入 QA / ship

## Round 31 — 2026-05-01 10:22

### 完成
- 接续 Trellis task `04-30-adult-search-fallback`，确认 `成人搜` adult-only fallback 已落地并保持在配置内成人 BT / Prowlarr 成人索引器边界
- 补强当前已配置成人源为空时的回复文案，明确给出下一步检查 `BT_WEB_SOURCES` 成人 BT 站点或 Prowlarr 成人索引器配置，并说明不会扩大到 PT 主线搜索
- 补充 focused regression 断言，保护空结果回复继续包含可操作下一步

### 测试状态
- 通过: 6 / 总计: 6

### 遗留 / 下轮继续
- `trellis-implement` 和 `trellis-check` 子 agent 均因 429 限流失败；本轮已在主线程执行同等 focused / lint / 主线 / adult BT wedge 验证
- 尚未执行 commit；下一步按 Trellis Phase 3.4 确认提交计划

### 下轮目标
- 确认并提交 `adult-search-fallback` 文案与测试补强，然后进入 `trellis-finish-work` 收尾

## Round 32 — 2026-05-01 17:24

### 完成
- 将 Telegram 成人 BT 搜索结果改为海报优先卡片：海报通过 Telegram photo 发送，作品信息和资源列表进入 HTML caption。
- 将成人 BT 磁力链接压缩为 `magnet:?xt=urn:btih:<hash>` 并用 `<code>` 包裹，去掉 `&dn=` / `&tr=` 等冗长参数。
- 为成人详情链接和首个资源下一步动作生成 inline keyboard：详情走 URL 按钮，下一步走短磁力 callback。
- 更新 `.trellis/spec/backend/bt-source-contracts.md` 的 Telegram adult result contract，避免后续按旧文本分层格式回退。

### 测试状态
- 通过: 6 / 总计: 6
- `focused adult/Telegram tests`
- `make lint`
- `make verify-stage1`
- `make quality`
- `make verify-mainline`
- `make verify-adult-bt-wedge`

### 遗留 / 下轮继续
- 当前仓库仍有大量本轮之前已存在的未提交改动；本轮未自动提交，避免混入无关变更。

### 下轮目标
- 若继续收口当前 Trellis task，先确认提交分组，再进入 `trellis-finish-work` 或后续 QA / 发布准备。

## Round 33 — 2026-05-01 18:00

### 完成
- 针对 `成人搜` Telegram 卡片补上可信中文化边界：标题、系列、演员优先使用 source/localized 字段、多源一致字段或本地 curated alias；日文原名保留为副标题。
- 新增 `app/services/adult_metadata_localization.py`，避免在 Telegram formatter 里硬编码翻译逻辑。
- 为 `SSIS-483` 这类当前反馈样例补回归测试：中文主标题、`七ツ森りり -> 七森莉莉`、日文原名保留；未知演员不盲翻并标记 `中文名未确认`。
- 同步 Trellis PRD、test-plan 和 backend source contract，明确“中文化”不是只翻字段标签。

### 测试状态
- 通过: 7 / 总计: 7
- `focused adult metadata/Telegram tests`
- `make lint`
- `make quality`
- `make verify-mainline`
- `make verify-adult-bt-wedge`
- `make verify-stage1`
- `git diff --check`

### 遗留 / 下轮继续
- 当前实现支持 source-provided localized 字段、多源一致字段和 curated alias；后续如要扩大覆盖面，应继续补更多演员/标题 alias 或把更多 metadata helper 的 localized 字段落进 `adult_metadata_candidates`。

### 下轮目标
- 提交本轮成人 metadata 中文化改动并重启本地 `app.main`，让 Telegram 实机测试使用最新代码。

## Round 34 — 2026-05-01 18:30

### 完成
- 把成人 metadata 中文化从“单番号 alias”升级为通用翻译 pipeline：adult-only 候选在 helper enrichment 后、formatter 前补齐中文标题、简介、系列、片商、厂牌和导演。
- 保持演员名 trust-only 边界：演员字段不走机器翻译；未知日文演员继续显示 `中文名未确认`。
- 补齐 fail-soft 留痕：无翻译 API key、翻译结果 request_id 不完整时会保留原始资源卡片，并写 operational log。
- Telegram 成人卡片新增 `简介` 和独立 `厂牌` 行，避免翻译字段被吞掉。
- 为 `main.py` 补回 startup wiring 测试，确保 adult metadata translation 复用 `subtitle_translation_*` 配置并注入 `SearchMediaService`。

### 测试状态
- 通过: 6 / 总计: 6
- `pytest tests/test_adult_metadata_translation.py tests/test_adult_metadata_localization.py tests/test_search_media.py tests/test_telegram_reply_formatter.py tests/test_main.py -q`
- `make lint`
- `make quality`
- `make verify-adult-bt-wedge`
- `git diff --check`

### 遗留 / 下轮继续
- 当前翻译留痕覆盖的是运行时主链使用的 `translate_candidates()` 路径；如果未来新增直接调用 `translate_requests()` 的调用方，需要同步补上同类留痕约束。

### 下轮目标
- 提交通用 adult metadata 翻译 pipeline，并重启本地运行进程，供 Telegram 实机验证 `成人搜 SSIS-842`。

## Round 35 — 2026-05-05 17:34

### 完成
- 为字幕翻译新增独立 `SUBTITLE_TRANSLATION_USE_PROXY` 开关，默认不复用全局 `OUTBOUND_PROXY_URL`
- 在 `app/main.py` 收口字幕翻译代理解析 helper，仅影响 `SubtitleTranslatorService` 装配
- 保留 repo-local `ffmpeg` 内嵌字幕提取修复，并补齐 focused tests 覆盖 config、main helper、subtitle translator 与本地 ffmpeg 提取路径

### 测试状态
- 通过: 10 / 总计: 10
- `.venv/bin/python -m pytest tests/test_config.py::test_load_settings_reads_token tests/test_config.py::test_load_settings_disables_subtitle_translation_proxy_by_default tests/test_config.py::test_load_settings_enables_subtitle_translation_proxy_when_requested tests/test_config.py::test_load_settings_rejects_invalid_subtitle_translation_use_proxy tests/test_main.py::test_build_ai_cast_localization_service_reuses_subtitle_translation_settings tests/test_main.py::test_resolve_subtitle_translation_proxy_url_defaults_to_disabled tests/test_main.py::test_resolve_subtitle_translation_proxy_url_uses_outbound_proxy_when_enabled tests/test_subtitle_translator.py::test_subtitle_translator_defaults_to_no_proxy tests/test_subtitle_translator.py::test_subtitle_translator_passes_proxy_to_httpx tests/test_subtitle_translator.py::test_translate_for_import_prefers_repo_local_ffmpeg_for_embedded_subtitle_extract`

### 遗留 / 下轮继续
- 当前仓库仍有本轮之前已存在的其他未提交改动；本轮未自动提交，避免混入无关变更。

### 下轮目标
- 若要进入收尾或提交，先按本轮文件边界确认 commit 分组。

## Round 36 — 2026-05-05 18:12

### 完成
- 复核 Telegram-first 观影 PT 主链，确认显式资源选择后已走 `add_by_selection_with_auto_confirm` / `add_by_candidate_with_auto_confirm`，用户面不再暴露下载 `confirm`。
- 复核下载完成后的默认硬链接导入路径，确认 `post_download_auto_import -> auto_import_by_task_ref` 已直接复用现有 import confirm execution tail，不再向用户暴露导入待确认文案；copy fallback 仍保留显式确认边界。
- 收紧 `tests/test_telegram_runtime_adapter.py` 的 PT 资源卡回调契约，明确断言 Telegram 回调直接返回最终“已添加下载”回包，而不是旧的待确认下载文案。

### 测试状态
- 通过: 3 / 总计: 3
- `./.venv/bin/python -m pytest -q tests/test_private_chat_selection_runtime.py tests/test_telegram_runtime_adapter.py tests/test_import_to_library.py tests/test_get_download_status.py tests/test_download_follow_up_runtime.py -k "auto_confirm or auto_import or pt_resource or download_follow_up or import_by_task_ref_with_auto_confirm or handle_digit_selection_query_routes_add_by_selection or handle_telegram_callback_query_consumes_pt_resource_card_without_shared_dispatch"`
- `./.venv/bin/python -m pytest -q tests/test_telegram_runtime_adapter.py tests/test_private_chat_selection_runtime.py tests/test_telegram_bot.py tests/test_telegram_reply_formatter.py -k "pt_resource or digit_selection or import_formats_import_approval_for_telegram or format_telegram_reply_formats_import_approval or format_telegram_reply_formats_add_approval"`

### 遗留 / 下轮继续
- 本轮只补了 Telegram PT 主链的行为回归，没有扩到 Feishu / personal WeChat / WeCom，也没有改 copy fallback、清理语义或字幕/provider/proxy 并行任务。

### 下轮目标
- 若进入收尾或提交，按 Telegram-first slice 与并行字幕任务分开做 commit 分组。

## Round 37 — 2026-05-06 19:58

### 完成
- 将下载完成后的 Telegram 自动导入主动通知从单条总结拆成四段式顺序通知：导入结果、字幕翻译结果、媒体库刷新结果、最终总结。
- 保持下载中的 Telegram live progress 原消息编辑链不变，同时补回 `get_download_status.py` 的 `status_label` 漏定义和下载完成轮询 interval 参数兼容。
- 收紧 `tests/test_get_download_status.py`、`tests/test_download_follow_up_runtime.py` 与 `tests/test_telegram_bot.py`，让四段式通知、新下载成功卡片和当前 scheduler 契约保持一致。

### 测试状态
- 通过: 3 / 总计: 3
- `.venv/bin/python -m pytest -q tests/test_get_download_status.py tests/test_download_follow_up_runtime.py`
- `make quality`
- `make verify-mainline`
- `make lint`

### 遗留 / 下轮继续
- 当前仓库仍有本轮之前已存在的其他未提交改动与 task 归档变更；本轮未自动提交，避免把无关文件混入同一批次。

### 下轮目标
- 若要提交或收尾，先按“四段式 TG 通知补丁”和其他并行中的 Telegram/UI 变更重新做 commit 分组。

## Round 38 — 2026-05-07 00:42

### 完成
- 收口 movie metadata 工件质量：目录型导入下的 metadata/NFO/图片产物改为覆盖写入，避免下载源自带 release NFO 和旧封面继续污染 Emby/Jellyfin 最终显示。
- 扩充 TMDB/Fanart 真相落盘：metadata sidecar / NFO 现已写出 `release_date`、`runtime_minutes`、`tagline`、关键 `crew`（导演/编剧/故事/剧本）以及 `poster/backdrop/logo/clearart/banner/disc/thumb` 资产矩阵。
- 修正 `job_event` 同 `task_id`/不同 `task_hash` 串号，避免 Telegram 完成态卡片把别的任务的字幕失败误合并进来。
- 收紧字幕跳过语义：GB18030/GBK 外挂字幕可读，中文内容外挂字幕不再误送翻译 provider，并在 Telegram 完成态卡片内显示 `字幕：✅ 已有中文字幕`。
- 现场对 `功夫熊猫 (2008)` 重跑 metadata / subtitle 判定，确认目录内已落 `poster.jpg`、`backdrop.jpg`、`logo.png`、`clearart.png`、`banner.jpg`、`disc.png`、`thumb.jpg` 与更新后的 XML NFO。

### 测试状态
- 通过: 5 / 总计: 5
- `.venv/bin/python -m pytest -q tests/test_metadata_scraper.py`
- `.venv/bin/python -m pytest -q tests/test_tmdb_client.py tests/test_fanart_client.py`
- `.venv/bin/python -m pytest -q tests/test_subtitle_translator.py -k "gb18030 or 中文字幕外挂字幕"`
- `.venv/bin/python -m pytest -q tests/test_import_to_library.py tests/test_get_download_status.py -k "chinese_ready or 中文字幕外挂字幕"`
- `.venv/bin/python -m pytest -q tests/test_persistence_sqlite.py tests/test_get_download_status.py tests/test_download_follow_up_runtime.py -k "job_event_repo_list_events_for_task_identity_requires_both_task_id_and_task_hash_when_both_present or telegram_live_progress or final_summary or auto_import"

### 遗留 / 下轮继续
- `country / studio / cast / crew` 的中文化仍不是完全拉满；当前主要靠 TMDB zh-CN truth 与现有 cast localization seam，尚未引入新的本地化 provider。
- 当前工作树仍混有 Telegram/status/字幕与 task bookkeeping 的并行未提交改动；提交时必须分组，不能一把梭。

### 下轮目标
- 若进入提交，先按 `metadata scrape quality overwrite and enrichment` 与 `telegram four-stage follow-up notifications` 两条主线拆 commit 组，再决定是否 push。

## Round 39 — 2026-05-07 14:06

### 完成
- 激活 `05-02-telegram-real-smoke-restore`，按任务研究与项目真相入口复核当前环境前置条件。
- 确认 `api.telegram.org` 的 DNS 已恢复，但宿主网络 `curl` 直连仍超时，且 `.env` 当前没有可用 `OUTBOUND_PROXY_URL`。
- 确认 `timeout 25 .venv/bin/python -m app.main` 可短时启动；当前 blocker 已从“本地进程未运行”收口为“Telegram 出口不可用，无法补真实入站 smoke”。
- 同步更新任务研究、`docs/STATUS.md` 与 `docs/BLOCKERS.md`，收口新的 operator-facing 真相。

### 测试状态
- 通过: 0 / 总计: 0
- 本轮仅做环境复核：`getent ahosts api.telegram.org`、宿主网络 `curl` 探针、`timeout 25 .venv/bin/python -m app.main`

### 遗留 / 下轮继续
- 在恢复可用 Telegram 出口前，`05-02-telegram-real-smoke-restore` 仍无法完成新的真实入站 smoke 证据闭环。

### 下轮目标
- 先恢复 `api.telegram.org` 的可用出口（直连或代理），保持本地 `app.main` 运行，再做一次真实 Telegram 入站复验。

## Round 40 — 2026-05-07 14:14

### 完成
- 用替代代理 `http://192.168.2.220:7890` 复核 Telegram 出口，确认代理端口可达。
- 通过该代理调用 Telegram Bot API `getMe`，确认响应为 `404 Not Found`，不是网络超时。
- 继续核对 `.env`，确认当前 `TELEGRAM_BOT_TOKEN` 为空（`token_len=0`）；带该代理短跑 `app.main` 时也只拉起了非 Telegram 宿主。
- 同步更新任务研究、`docs/STATUS.md`、`docs/BLOCKERS.md`，将当前 blocker 从“代理出口缺失”收口为“Telegram token 为空”。

### 测试状态
- 通过: 0 / 总计: 0
- 本轮仅做环境复核：代理 `curl` 探针、Telegram `getMe`、`token_len` 形态检查、带代理 `timeout 25 .venv/bin/python -m app.main`

### 遗留 / 下轮继续
- 在补回有效 `TELEGRAM_BOT_TOKEN` 前，`05-02-telegram-real-smoke-restore` 仍无法恢复 Telegram 宿主并补新的真实入站 smoke。

### 下轮目标
- 先恢复有效 `TELEGRAM_BOT_TOKEN`，再通过 `http://192.168.2.220:7890` 复跑 `getMe` 与真实 Telegram 入站 smoke。

## Round 41 — 2026-05-07 14:32

### 完成
- 纠正上一轮 shell 探针的引号错误，确认“`TELEGRAM_BOT_TOKEN` 为空”并非 `.env` 真相。
- 重新验证 `.env`：`TELEGRAM_BOT_TOKEN` 非空且格式正确；当前默认 `OUTBOUND_PROXY_URL` 也非空。
- 通过替代代理 `http://192.168.2.220:7890` 重跑 Telegram Bot API `getMe`，确认返回 `200` 且响应体 `ok=true`。
- 同步修正任务研究、`docs/STATUS.md`、`docs/BLOCKERS.md`，把当前状态收口为“环境前置条件已恢复，等待新的真实 Telegram 入站 smoke”。

### 测试状态
- 通过: 0 / 总计: 0
- 本轮仅做环境复核：安全长度/形态检查、修正后的 `getMe` 探针、带代理 `timeout 25 .venv/bin/python -m app.main`

### 遗留 / 下轮继续
- 当前还缺一条本会话内的新真实 Telegram 入站消息证据。

### 下轮目标
- 保持 `app.main` 运行并接收一条真实 Telegram 消息，补齐 smoke 证据链。

## Round 42 — 2026-05-07 15:23

### 完成
- 复查 `logs/trace.log`，确认当前会话已收到新的真实 Telegram 入站消息：`ping` 与 `start`。
- 确认同会话 reply 也已发出：`候选作品：ping ✓` 与 `候选作品：start ✓`，证明入站与回包链路已恢复。
- 将新的真实 Telegram 入站证据同步回任务研究、`docs/STATUS.md`、`docs/BLOCKERS.md`。

### 测试状态
- 通过: 0 / 总计: 0
- 本轮仅做真实环境复核：运行态 `app.main` + `logs/trace.log` 证据检查

### 遗留 / 下轮继续
- 当前仍缺同会话 `PT 资源选择 -> 下载 -> 导入/后处理` 的新实测证据。

### 下轮目标
- 在 `app.main` 继续运行的前提下，补一条新的 PT 后半段真实 Telegram smoke 链路。

## Round 43 — 2026-05-07 15:42

### 完成
- 复查 `logs/trace.log`，确认当前会话已补到新的 PT 后半段真实证据：`功夫熊猫 -> 候选作品 -> PT 资源卡 -> confirm dispatch -> 下载状态 ✓`。
- 复查 `job_event` 与 `download_monitor`，确认 `46b907...` 在本轮新增了 `downloader.succeeded` 与 `downloader.completed_observed`，且当前状态为 `status_code=6`、`percent_done=1.0`、`is_complete=1`。
- 确认本轮没有新增 `import.* / metadata.* / subtitle.* / refresh.*` 事件；所选标题复用了既有任务 hash，因此同会话导入/后处理证据仍未刷新。
- 同步更新任务研究、`docs/STATUS.md`、`docs/BLOCKERS.md`。

### 测试状态
- 通过: 0 / 总计: 0
- 本轮仅做真实环境复核：`logs/trace.log`、`job_event`、`download_monitor`

### 遗留 / 下轮继续
- 当前还缺一条“新 hash / 新导入”的同会话导入与后处理证据。

### 下轮目标
- 选择一个未复用既有下载/导入记录的 PT 标题，补齐同会话 `导入/metadata/字幕/刷新` 证据。

## Round 44 — 2026-05-07 16:00

### 完成
- 复查 `logs/trace.log`，确认当前会话已补到第二条 fresh-hash PT 证据：`超人 -> 候选作品 -> PT 资源卡 -> 已添加下载 -> 下载状态 ⏳`。
- 复查 `job_event` 与 `download_monitor`，确认新 hash `52bde7...` 已生成 `media.identity.confirmed`、`downloader.succeeded`，当前 `status_code=4`、`percent_done≈0.00447`、`is_complete=0`。
- 确认当前不是环境阻断；剩余问题只是等待这条 fresh hash 下载完成后，继续观察新的 `import.* / metadata.* / subtitle.* / refresh.*` 事件。
- 同步更新任务研究、`docs/STATUS.md`、`docs/BLOCKERS.md`。

### 测试状态
- 通过: 0 / 总计: 0
- 本轮仅做真实环境复核：`logs/trace.log`、`job_event`、`download_monitor`

### 遗留 / 下轮继续
- `52bde7...` 仍在下载中，新的导入与后处理事件尚未出现。

### 下轮目标
- 等待 `52bde7...` 下载完成，并补齐同会话 `导入/metadata/字幕/刷新` 证据。

## Round 45 — 2026-05-07 16:28

### 完成
- 对 fresh hash `52bde7...` 在重启前记录进度卡片快照：`3%`、`telegram_progress_last_synced_at=08:26:18`。
- 重启 `app.main` 使修复生效，并持续观察同一条 `download_monitor` 记录。
- 确认重启后同一张 Telegram 进度卡片继续同步：`telegram_progress_last_synced_at` 先推进到 `08:27:57`，再推进到 `08:28:10`，持久化文本也从 `3%` 刷到 `4%`。
- 同步更新任务研究、`docs/STATUS.md`、`docs/BLOCKERS.md`，把“重启后卡片继续更新”实测结果落成 operator-facing 真相。

### 测试状态
- 通过: 24 / 总计: 24
- `./.venv/bin/python -m pytest -q tests/test_download_follow_up_runtime.py`
- `./.venv/bin/python -m pytest -q tests/test_get_download_status.py -k "telegram_live_progress or post_processing or summary_sent"`

### 遗留 / 下轮继续
- `52bde7...` 仍在下载中，新的导入与后处理事件尚未出现。

### 下轮目标
- 等待 `52bde7...` 下载完成，并继续抓取同会话 `导入/metadata/字幕/刷新` 证据。

## Round 46 — 2026-05-07 19:48

### 完成
- 复查 `52bde7...` 的 `job_event`，确认 fresh hash `超人` 已完整走到 `import.succeeded`、`metadata.succeeded`、`subtitle.skipped`、`refresh.succeeded`、`telegram.summary_sent`。
- 删除 Telegram 渠道里多余的 `查看状态` 入口：`已添加下载` 消息不再附带该按钮，实时进度卡片也不再附带该按钮。
- 保留 Telegram 实时进度卡片和最终总结通知，避免和已有的实时状态链路重复。

### 测试状态
- 通过: 7 / 总计: 7
- `./.venv/bin/python -m pytest -q tests/test_telegram_delivery_runtime.py tests/test_telegram_runtime_adapter.py tests/test_telegram_reply_formatter.py tests/test_download_follow_up_runtime.py -k "查看状态 or status_only_action or add_success or live_progress or resumes_completed_telegram_card_after_restart or edits_bound_telegram_message_and_dedupes_same_status"`

### 遗留 / 下轮继续
- 当前工作树仍混有 Telegram smoke、metadata、task bookkeeping 等并行未提交改动；提交时必须按主线拆组。

### 下轮目标
- 整理 commit 分组，先提交 Telegram smoke / progress card / TG 渠道按钮收口这条主线。

## Round 47 — 2026-05-07 22:43

### 完成
- 基于当前真实代码新增 `docs/flows/` 文档集合，拆分为启动装配、shared private-chat 主链、下载/导入/cleanup、BT/成人/订阅、SQLite 真相层五组流程文档，并补充目录索引。
- 逐段复核 `app/main.py`、`app/bot/private_chat_runtime.py`、`app/services/*`、`app/db/*`，把“入口 -> 路由 -> 副作用 -> 落盘”的真实链路反写成可导航文档。
- 确认新增流程文档没有打坏 docs gate：`tests/test_cleanup_docs_consistency.py` 继续通过。
- 记录当前仓库级验证现状：`make quality` / `make lint` 与 `make verify-mainline` 仍存在既有红灯，本轮不改业务代码，只把失败点写入 `docs/BLOCKERS.md`。

### 测试状态
- 通过: 1 / 总计: 4
- `./.venv/bin/python -m pytest tests/test_cleanup_docs_consistency.py`
- 失败: `make quality`（`app/bot/telegram_update_runtime.py:240` 存在未使用局部变量 `task_identity`）
- 失败: `make lint`（同上）
- 失败: `make verify-mainline`（`tests/test_telegram_bot.py` 中 2 条既有断言与当前状态文案不一致）

### 遗留 / 下轮继续
- 若要把仓库重新拉回全绿，需要单独修复当前既有 lint / verify 失败；这不是本轮流程文档反写直接引入的问题。

### 下轮目标
- 若继续做收尾验证，先单独处理 `telegram_update_runtime.py` 的 lint 红灯和 `tests/test_telegram_bot.py` 的状态文案断言漂移，再重跑全仓验证。

## Round 48 — 2026-05-07 23:55

### 完成
- 把 `docs/flows/` 反向接入顶层真相文档：`docs/INDEX.md` 新增 AI / 开发者阅读路径入口，`docs/PRD.md` 与 `docs/ARCHITECTURE.md` 改写为当前代码口径。
- 收口摘要层漂移：明确数字选资源与 `import <ref>` 是 guarded auto-confirm，direct source / BT follow-up / duplicate override / copy-fallback 仍需显式 `confirm`；同步写明 capability-based 宿主、Telegram-first callback 主链、WeCom 主动发送 unsupported、pure BT 兼容分支定位。
- 修复 `docs/STATUS.md` 与 `docs/NEXT_STEP.md` 对最新真实 Telegram smoke 的冲突，并把 `docs/SEARCH_REPLY_PRESENTATION_PLAN.md` 标记为 superseded。
- 补 docs gate：`tests/test_cleanup_docs_consistency.py` 新增 `docs/flows/INDEX.md` 入口检查，以及 `STATUS/NEXT_STEP` 对“最新真实 Telegram smoke 已存在”的一致性断言。

### 测试状态
- 通过: 11 / 总计: 11
- `./.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`
- 失败: `make quality`（既有红灯：`app/bot/telegram_update_runtime.py:240` 未使用局部变量 `task_identity`）
- 失败: `make lint`（同上）
- 失败: `make verify-mainline`（既有红灯：`tests/test_telegram_bot.py` 两条断言仍期待旧文案 `等待下载器首次同步`）

### 遗留 / 下轮继续
- 当前文档纠偏已完成，但仓库级全绿仍被既有 lint / mainline 失败阻断；这两处失败不是本轮 docs 改动引入。

### 下轮目标
- 若继续做收尾验证，先单独处理 `app/bot/telegram_update_runtime.py` 的 pyflakes 红灯和 `tests/test_telegram_bot.py` 的旧状态文案断言，再重跑 `make quality`、`make lint`、`make verify-mainline`。

## Round 49 — 2026-05-08 00:13

### 完成
- 根据 `trellis-check` 审查补强 docs gate，把这轮新增的摘要层真相一并锁进 `tests/test_cleanup_docs_consistency.py`。
- 新增对审批边界、capability-based 宿主、Telegram-first callback、WeCom 主动发送 unsupported、pure BT 隐藏兼容分支，以及 `SEARCH_REPLY_PRESENTATION_PLAN.md` superseded 状态的断言。
- 同步把“最新真实 Telegram smoke 已存在”这一轮的 spec 学习写回 `.trellis/spec/backend/quality-guidelines.md`。

### 测试状态
- 通过: 12 / 总计: 12
- `./.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

### 遗留 / 下轮继续
- 仓库级 `make quality` / `make lint` / `make verify-mainline` 仍被既有 runtime / test 红灯阻断，和本轮新增 docs gate 无关。

### 下轮目标
- 若继续收尾，整理 commit 分组并确认是否连同既有未识别脏文件一起提交；若要拉回全绿，再单独修复现有 lint 与 `tests/test_telegram_bot.py` 断言漂移。
