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
