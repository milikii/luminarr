# Next step (v188)

## Current goal

- 当前唯一主线：**four-channel cleanup verification baseline**
- 当前窗口：`2026-04-05 to 2026-04-12`
- 详细台账和证据统一写在 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- cleanup 详细窗口规则和证据：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- 知识入口：`README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md`

## Only do

- 完成一个 7 天真实使用验证窗口，不新增任何 cleanup 行为。
- 保持 Telegram / personal WeChat / Feishu / WeCom 四个渠道都可用，且继续共用同一套 shared runtime、workflow、approval、`jobs` 和 SQLite 真相。
- 持续记录窗口起止日期、四渠道真实私聊 smoke 进度、窗口活性、当前结论、最近一次 smoke gate / cleanup 协议回归 / verification docs gate 到 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
- 保持仍在进行中的 cleanup 验证窗口快照和最近一次验证日期同步到当天绝对日期，避免窗口台账和 `docs/STATUS.md` 停留旧日期。
- 保持 `docs/STATUS.md` 只保留快照，不把窗口详细规则和备注明细抄回去。
- 保持 `README.md` 只同步仓库入口需要知道的当前边界、cleanup 风险和后续路线；窗口逐项证据继续只写在 `docs/CLEANUP_VERIFICATION_WINDOW.md` / `docs/STATUS.md`。
- 保持 `README.md` 当前 next step 的退出条件也显式覆盖 `verification docs gate`，避免用户只看仓库入口时误以为 docs gate 不是 cleanup 验证窗口的正式退出条件。
- 保持 verification docs gate 继续显式校验 `README.md` 的十条 cleanup 本地 gate 入口仍写明“不能替代四渠道真实私聊 smoke 证据”，避免用户把本地 pytest / docs gate 误读成真实渠道退出证据。
- 保持历史单体主文档 `Luminarr_v15.md` 不再作为当前知识入口，避免过期总纲和 `README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md` 这条正式入口重新分叉。
- 保持 `docs/GETTING_STARTED.md` 明确区分“能启动应用”和“能补当前 cleanup 验证窗口四渠道真实私聊 smoke 证据”的前置条件，避免把本地回归误当成真实渠道验证。
- 保持 `.env.example` 用中文详细说明每个变量的作用、默认值语义，以及“只为启动最小本地测试”时真正必填的变量集合，避免把配置模板误读成完整渠道准备状态。
- 保持 `.env.example` 对 `DOWNLOADER_INSTANCES` / `PT_DOWNLOADER` / `BT_DOWNLOADER` / `RAW_BT_DESTINATIONS` / `BT_WEB_SOURCES` / `FEISHU_*` / `WECOM_*` 继续写清中文作用、取值格式和默认语义，避免用户拿到 token 后仍不知道其他必需字段该填什么。
- 保持 `Makefile` 同时提供独立的四渠道 cleanup smoke gate 入口和当前 cleanup 验证窗口的一键 gate 入口，避免把 smoke gate、cleanup 聚合回归和 docs gate 混成一条不透明命令。
- 保持 `Makefile` 明确暴露 `test-cleanup-docs-gate`，让 cleanup verification docs gate 和普通 `test-docs` 分开，避免把 docs consistency gate 误当成当前 cleanup 窗口的完整文档 gate。
- 保持 `Makefile` 明确暴露 `test-cleanup-service-not-ready`，让 cleanup service-not-ready observability 有独立 gate，避免这条专项 smoke 只能从 `docs/STATUS.md` 里的底层 pytest 命令回推。
- 保持 `Makefile` 明确暴露 `test-cleanup-telegram`，让 Telegram cleanup 入口回归有稳定入口，避免 `docs/STATUS.md` 里的单渠道回归仍只能靠底层 pytest 命令手敲。
- 保持 `Makefile` 明确暴露 `test-cleanup-personal-wechat`，让 personal WeChat cleanup 入口回归有稳定入口，避免这个私聊渠道的 cleanup 回归仍只能从聚合 gate 里拆命令。
- 保持 `Makefile` 明确暴露 `test-cleanup-feishu`，让 Feishu cleanup 入口回归有稳定入口，避免这个私聊渠道的 cleanup 回归仍只能从聚合 gate 里拆命令。
- 保持 `Makefile` 明确暴露 `test-cleanup-wecom`，让 WeCom cleanup 入口回归有稳定入口，避免这个私聊渠道的 cleanup 回归仍只能从聚合 gate 里拆命令。
- 保持 `Makefile` 明确暴露 `test-cleanup-feishu-webhook`，让 Feishu webhook cleanup 入口回归有稳定入口，避免这个加密 webhook 路径只能从文档示例间接回推。
- 保持 `Makefile` 明确暴露 `test-cleanup`，让 cleanup 聚合回归有稳定入口，避免窗口 gate 仍只能从 `test-cleanup-window` 反推第二段命令。
- 保持 `README.md` / `docs/GETTING_STARTED.md` 继续提供无 `make` 环境下的等价一行 pytest 备用命令，至少显式覆盖 `test-cleanup-service-not-ready`、`test-cleanup-telegram`、`test-cleanup`、`test-cleanup-docs-gate` 和 `test-cleanup-window`，避免把 Makefile 当成当前 cleanup 窗口 gate 的唯一入口。
- 保持 verification docs gate 继续显式校验 `test-cleanup-window` 仍按 `smoke gate -> cleanup 聚合回归 -> verification docs gate` 顺序执行，且 `docs/GETTING_STARTED.md` 里的无 `make` 备用命令与这三段 Makefile 入口保持一致，避免窗口 gate 入口拆成多份后互相漂移。
- 保持 `docs/GETTING_STARTED.md` / `docs/TEST_ENV.md` 对 Transmission / Emby 本地测试栈的 compose 文件位置、启动命令和配置目录位置保持一致，避免把不存在的目录误写成 compose 根目录。
- 保持 `docs/STATUS.md` 里的 tests / cleanup service / compile check / docs consistency check 都带绝对日期，避免这些本地验证快照比 smoke / docs gate 更难判断是否过期。
- 保持 cleanup 验证窗口仍在进行中时，`docs/CLEANUP_VERIFICATION_WINDOW.md` 的 smoke gate / cleanup 协议回归 / verification docs gate 日期，与 `docs/STATUS.md` 的 tests / cleanup service / compile check / docs consistency check 一起滚动到当天绝对日期，避免只更新半套快照。
- 保持 `tests/test_cleanup_cross_channel_smoke.py` 稳定，继续作为四渠道 cleanup discoverability / inspect / execution / rejection guidance / post-cleanup confirmation / mixed-case english cleanup protocol / `chat-scoped task_ref -> jobs -> import correlation` / correlation-query-failure identity retention / missing-structured-import-correlation identity retention 的聚合 smoke gate。
- 保持 `tests/test_telegram_bot.py -k cleanup` 单独覆盖 Telegram cleanup mixed-case 英文 `cleanup / cleanup inspect` 入口路由，避免 Telegram 渠道胶水大小写回退只能等聚合 smoke 才暴露。
- 保持 README / STATUS 对 cleanup 聚合 smoke gate 的入口描述也同步覆盖 mixed-case 英文 `cleanup / cleanup inspect` 输入、`job_event` 关联查询失败、缺结构化 `source_path/target_path` 两类 identity retention / rejection guidance，以及 `guard-rejected` rejection guidance，避免入口文档落后于当前 gate。
- 保持 verification docs gate 继续显式校验 `mixed-case english cleanup protocol` 命名观察，避免窗口台账把英文字母大小写输入边界写丢。
- 保持 verification docs gate 继续显式校验 `NEXT_STEP current-window sync`，避免 `docs/NEXT_STEP.md` 里的 `当前窗口` 日期和 `docs/CLEANUP_VERIFICATION_WINDOW.md` 的窗口日期只改一处。
- 保持 verification docs gate 继续显式校验 `correlation-query-failure observability` 命名观察，避免窗口台账把这类 query failure 可观测性写丢。
- 保持 verification docs gate 继续显式校验 `source-type-unsupported blocked-log observability` 命名观察，避免窗口台账把这类阻断日志可观测性写丢。
- 保持 verification docs gate 继续显式校验 `cleanup-service-not-ready fix-hint observability` 命名观察，避免窗口台账把 cleanup service 未注入时的红色日志和处理建议写丢。
- 保持 `tests/test_private_chat_runtime.py` 单独覆盖 shared runtime 直调路径的 cleanup service-not-ready observability，避免这条共享入口只能靠四渠道 smoke 侧面兜底。
- 保持 `tests/test_telegram_bot.py -k "cleanup and service_not_ready"` 单独覆盖 Telegram cleanup service-not-ready observability，避免这个渠道的 cleanup 命令入口只能靠聚合 smoke 或非 cleanup service-not-ready 测试间接兜底。
- 保持 `tests/test_personal_wechat_text.py` 单独覆盖 personal WeChat cleanup service-not-ready observability，避免这个渠道的单条消息处理和轮询发消息路径只能靠聚合 smoke 间接兜底。
- 保持 `tests/test_feishu_adapter.py` 单独覆盖 Feishu 私聊入口 cleanup service-not-ready observability，避免这个渠道的私聊入站链路只能靠聚合 smoke 间接兜底。
- 保持 `tests/test_feishu_adapter.py -k "webhook_http_request and cleanup"` 单独覆盖 Feishu webhook cleanup 路由和 service-not-ready observability，避免这个加密 webhook 入口只有正常路径回归、缺少未注入服务时的可观测性保护。
- 保持 `tests/test_wecom_adapter.py` 单独覆盖 WeCom 私聊入口 cleanup service-not-ready observability，避免这个渠道的解密入站和加密回包路径只能靠聚合 smoke 间接兜底。
- 保持 `docs/STATUS.md` 里的 WeCom cleanup service-not-ready 快照和 Latest verification 同步到同一组跑数，避免同一轮结果在同一文件里写出两套数字。
- 保持 verification docs gate 继续显式校验 `success-event-append-failure observability` 命名观察，避免窗口台账把这类事件落盘失败可观测性写丢。
- 保持 verification docs gate 继续显式校验 `delete-failure observability` 命名观察，避免窗口台账把这类删除失败可观测性写丢。
- 保持 verification docs gate 继续显式校验 `correlation-missing unresolved-identity blank display` 命名观察，避免窗口台账把这条空白身份展示边界写丢。
- 保持 verification docs gate 继续显式校验 `correlation-missing inspect identity resolution` 命名观察，避免窗口台账把 chat-scoped inspect 身份解析成功后的文本边界写丢。
- 保持 verification docs gate 继续显式校验 `correlation-missing rejection guidance` 命名观察，避免窗口台账把这类关联缺失后的 follow-up 引导写丢。
- 保持 verification docs gate 继续显式校验 `post-cleanup cleanup inspect confirmation` 命名观察，避免窗口台账把 cleanup 成功后的复核文本边界写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref post-cleanup cleanup inspect confirmation` 命名观察，避免窗口台账把 chat-scoped cleanup 成功后的复核文本边界写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref target-missing cleanup inspect follow-up guidance` 命名观察，避免窗口台账把 chat-scoped target-missing inspect follow-up 写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref source-missing cleanup inspect follow-up guidance` 命名观察，避免窗口台账把 chat-scoped source-missing inspect follow-up 写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref source-type-unsupported cleanup inspect follow-up guidance` 命名观察，避免窗口台账把 chat-scoped source-type inspect follow-up 写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref guard-rejected cleanup inspect follow-up guidance` 命名观察，避免窗口台账把 chat-scoped guard-rejected inspect follow-up 写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref target-missing rejection guidance` 命名观察，避免窗口台账把 chat-scoped target-missing 阻断后的 follow-up 引导写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref source-missing rejection guidance` 命名观察，避免窗口台账把 chat-scoped source-missing 阻断后的 follow-up 引导写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref source-type-unsupported rejection guidance` 命名观察，避免窗口台账把 chat-scoped source-type 阻断后的 follow-up 引导写丢。
- 保持 verification docs gate 继续显式校验 `source-type-unsupported rejection guidance` 命名观察，避免窗口台账把这类 source-type 阻断后的 follow-up 引导写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref guard-rejected rejection guidance` 命名观察，避免窗口台账把这类 chat-scoped guard-rejected 阻断后的 follow-up 引导写丢。
- 保持 verification docs gate 继续显式校验 cleanup 窗口写成 `已完成` 后，`当前 cleanup 协议观察` 不再残留 `尚未到最早可结束日期`、`已到最早可结束日期` 或 `真实私聊 cleanup smoke` 待补文案，避免窗口已收口后台账还挂着进行中阻塞文本。
- 在 cleanup 验证窗口正式退出前，至少评估并记录 PT 下载任务的做种状态 guardrail（`pt_min_seed_hours` 保护、下载器 seeding 信息等）是否已在 guardrail 里覆盖；窗口台账里必须明确写出“当前 cleanup guardrail 未读取下载器 seeding 状态、`pt_min_seed_hours` 未进入 cleanup 阻断判断、因此本窗口只记录风险，不扩 cleanup 行为”。
- 保持 cleanup 身份展示边界稳定：只有 `chat-scoped task_ref` 真正从 `jobs` 解析出身份时才回显和记录 `task_id/task_hash`；普通 correlation-missing inspect 继续显示 `-`，cleanup follow-up 继续落到稳定的 hash / id。
- 保持 `chat-scoped task_ref` 在 `job_event` 关联查询失败时也继续打印 resolved `lookup_task_ref/task_id/task_hash`，且 inspect / cleanup 文本不要丢掉已解析出的身份。
- 保持 `chat-scoped task_ref` 命中历史 `import.succeeded` 但缺 `source_path/target_path` 时，也继续回显 resolved identity，并保持 correlation-missing 文本协议不变。
- 保持 `chat-scoped task_ref` 在真正执行 cleanup 但删除失败时，也继续使用已解析出的真实任务身份写 `cleanup.failed` 事件和红色日志。
- 保持 `chat-scoped task_ref` 在 cleanup 已成功但 `cleanup.succeeded` 事件写入失败时，也继续打印真实任务身份，且不隐藏成功文本。
- 保持 `chat-scoped task_ref` 在 guardrail 判成 `source_type_unsupported` 时，也继续用真实关联任务身份打印阻断日志和 follow-up。
- 保持 cleanup service 未注入时，`cleanup` / `cleanup inspect` 也继续打印红色中文 `[cleanup 服务未就绪]` 日志、`动作=cleanup/cleanup_inspect`、`查询=` 与 `[处理建议]` 修复提示，避免四渠道只回 `SERVICE_NOT_READY_TEXT` 却没有运维可见性。
- 保持 cleanup 失败可观测性稳定：
  - 删除失败日志：`[cleanup 执行失败] + event_type=cleanup.failed + task_ref + source + target`
  - 关联查询失败日志：`task_ref + lookup_task_ref/task_id/task_hash`
  - 事件写入失败日志：`task_ref + task_id/task_hash + source + target`
- 只允许修：
  - shared runtime 回归
  - 渠道适配胶水回归
  - 显式中文日志和修复提示缺口
- 保持 bring-up 入口稳定：
  - `.env.example`
  - `Makefile`
  - `Dockerfile`
  - `docker-compose.yml`
  - `docs/GETTING_STARTED.md`

## Do not do

- 不新增自动 inspect、自动 cleanup、批量 cleanup、删种或新的 cleanup workflow。
- 不放宽现有 cleanup guardrail、删除范围或 correlation 校验。
- 不把四渠道适配重构成通用多渠道平台、通用 webhook 总线或通用 plugin / skill / MCP 平台。
- 不在这一步启动 `series / anime` 实现、shared private-chat 交付体验 polish、最小人类可用入口之外的新产品面、BT 共享评分器重写、Jellyfin / Plex 支持或其他新集成。
- 不回退现有文本协议：
  - `cleanup inspect <任务ID或Hash>` / `清理检查 <任务ID或Hash>`
  - `cleanup <任务ID或Hash>` / `清理 <任务ID或Hash>`
  - bare `cleanup` / `清理`
  - bare `cleanup inspect` / `清理检查`

## Done when

- 已完成 7 天验证窗口。
- 四个渠道各至少完成 1 次真实私聊 shared-runtime smoke。
- `tests/test_cleanup_cross_channel_smoke.py` 持续通过。
- cleanup discoverability / inspect / execution / rejection guidance / success follow-up / failure observability 没有协议回退。
- `docs/CLEANUP_VERIFICATION_WINDOW.md` 已完整记录窗口起止日期、证据、当前状态和当前结论。
- `docs/STATUS.md` 快照、`docs/NEXT_STEP.md` 目标和窗口台账保持一致。

## After this step

1. 独立后台下载完成轮询（复用 `download_monitor` 和现有 `PostDownloadAutoImportService`，不扩成通用 scheduler 平台）。
2. `series / anime` 独立名称解析最小实现（结构化解析 + 小型识别词/替换配置，parser-first，不做 DSL）。
3. `.ass` 字幕支持评估与最小实现（与 `series / anime` 同步收口）。
4. shared private-chat 交付体验收口（图片 / 信息卡片 / 字符排版 / 状态信息清晰化，不做 Web UI）。
5. 最小人类可用入口继续补齐（quick start / 配置模板 / 首个渠道 10 分钟跑通）。
6. BT 共享确定性评分器。
7. Jellyfin / Plex 支持（后续）。
8. plugin 体系继续后置。
