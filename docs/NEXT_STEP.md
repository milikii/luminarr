# Next step (v244)

## Current goal

- 当前进行中的 promoted 主线仍是 **Telegram 后台 completion polling 直连共享 follow-up helper 收口**。
- 当前最小闭环是：只把 `telegram_bot._poll_pending_download_completion_once()` 从 `get_status_text()` 的间接副作用里拆出来，改成直接复用共享 helper。
- 这一步继续只做最小 repo / orchestration 降本，不顺手放大成新的 service 大重构。
- 当前主线细节继续看 `docs/PERSISTENCE_CLOSURE_LOG.md` 与 `docs/GET_DOWNLOAD_STATUS_SLIMMING_LOG.md`。

## User value

- 让后台轮询、状态观察、完成事件和自动导入继续围绕同一份 `download_monitor` / `job_event` 真相工作。
- 减少渠道层的隐式副作用，降低后续 fork 维护者读代码和改代码时的误判成本。

## Only do

- 只做 Telegram 后台 completion polling 直连共享 helper 的最小结构降本。
- 保持 `download_monitor`、`job_event`、`AutoImportStateUnavailableError`、中文日志和现有状态 follow-up 语义不回退。
- 保持 `get_download_status.py`、`post_download_auto_import.py`、`telegram_bot.py` 的现有对外协议不变。
- 文档继续分层：`STATUS.md` 只写当前快照；详细结论继续收口到 `docs/PERSISTENCE_CLOSURE_LOG.md`。

## Do not do

- 不放宽 approval、`jobs` / `job_event` / lease/version / SQLite 真相边界。
- 不新增自动导入规则，不改低质量过滤语义，不改 `AutoImportRunResult` 字段含义。
- 不把这一步直接放大成更大的渠道层重构、下载器平台化、自动 `confirm` 或 refresh 大主线。
- 不回到 BT 页面 proof、BT dispatch 取证或 Plex 实例追查。

## Done when

当前 **Telegram 后台 completion polling 直连共享 follow-up helper 收口** 主线视为 **已收口**，满足以下任一条即可：

1. `telegram_bot._poll_pending_download_completion_once()` 不再通过 `get_status_text()` 间接触发共享副作用，而是直接复用共享 helper 推进状态观察落盘、完成事件追加和自动导入消费，并保持现有中文日志、停路语义和对外协议不变；
2. focused tests 能继续覆盖状态查询、状态 follow-up、后台 completion polling 与自动导入最小回归；
3. 文档继续保持分层一致，`STATUS.md` 只写当前快照，详细结论继续收口到 `docs/PERSISTENCE_CLOSURE_LOG.md`。

## After this step

1. 如果这条 Telegram 后台 polling 直连 helper 收口完成，就继续在同一职责族里挑下一段最小 repo / orchestration 降本点。
2. 如果这条 Telegram 后台 polling 直连 helper 证明不值得继续细拆，就回到同一职责族里再找一个更小、更保守的结构降本点。
3. 如果后续单独拿到 Plex 实例，再开一条最小 Plex real smoke 主线。
