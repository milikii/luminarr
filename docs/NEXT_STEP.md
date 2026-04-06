# Next step (v164)

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
- 保持 `docs/STATUS.md` 只保留快照，不把窗口详细规则和备注明细抄回去。
- 保持 `README.md` 只同步仓库入口需要知道的当前边界、cleanup 风险和后续路线；窗口逐项证据继续只写在 `docs/CLEANUP_VERIFICATION_WINDOW.md` / `docs/STATUS.md`。
- 保持 `tests/test_cleanup_cross_channel_smoke.py` 稳定，继续作为四渠道 cleanup discoverability / inspect / execution / rejection guidance / post-cleanup confirmation / `chat-scoped task_ref -> jobs -> import correlation` / correlation-query-failure identity retention / missing-structured-import-correlation identity retention 的聚合 smoke gate。
- 保持 README / STATUS 对 cleanup 聚合 smoke gate 的入口描述也同步覆盖 `job_event` 关联查询失败、缺结构化 `source_path/target_path` 两类 identity retention / rejection guidance，避免入口文档落后于当前 gate。
- 保持 verification docs gate 继续显式校验 `correlation-query-failure observability` 命名观察，避免窗口台账把这类 query failure 可观测性写丢。
- 保持 verification docs gate 继续显式校验 `source-type-unsupported blocked-log observability` 命名观察，避免窗口台账把这类阻断日志可观测性写丢。
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
- 保持 verification docs gate 继续显式校验 `source-type-unsupported rejection guidance` 命名观察，避免窗口台账把这类 source-type 阻断后的 follow-up 引导写丢。
- 在 cleanup 验证窗口正式退出前，至少评估并记录 PT 下载任务的做种状态 guardrail（`pt_min_seed_hours` 保护、下载器 seeding 信息等）是否已在 guardrail 里覆盖；窗口台账里必须明确写出“当前 cleanup guardrail 未读取下载器 seeding 状态、`pt_min_seed_hours` 未进入 cleanup 阻断判断、因此本窗口只记录风险，不扩 cleanup 行为”。
- 保持 cleanup 身份展示边界稳定：只有 `chat-scoped task_ref` 真正从 `jobs` 解析出身份时才回显和记录 `task_id/task_hash`；普通 correlation-missing inspect 继续显示 `-`，cleanup follow-up 继续落到稳定的 hash / id。
- 保持 `chat-scoped task_ref` 在 `job_event` 关联查询失败时也继续打印 resolved `lookup_task_ref/task_id/task_hash`，且 inspect / cleanup 文本不要丢掉已解析出的身份。
- 保持 `chat-scoped task_ref` 命中历史 `import.succeeded` 但缺 `source_path/target_path` 时，也继续回显 resolved identity，并保持 correlation-missing 文本协议不变。
- 保持 `chat-scoped task_ref` 在真正执行 cleanup 但删除失败时，也继续使用已解析出的真实任务身份写 `cleanup.failed` 事件和红色日志。
- 保持 `chat-scoped task_ref` 在 cleanup 已成功但 `cleanup.succeeded` 事件写入失败时，也继续打印真实任务身份，且不隐藏成功文本。
- 保持 `chat-scoped task_ref` 在 guardrail 判成 `source_type_unsupported` 时，也继续用真实关联任务身份打印阻断日志和 follow-up。
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
