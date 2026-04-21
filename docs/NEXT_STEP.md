# Next step (v294)

## Current goal

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 正式宣告收工；当前阶段切到 **services 层数据结构降本**，Done 定义锁在"三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- 当前阶段第 1 条主线已完成：**`app/services/import_to_library.py` 数据结构重设计 · 第 1 轮 · 路径与特殊分支清单** 已落到 `docs/IMPORT_PIPELINE_REDESIGN.md`。
- 当前阶段第 2 条主线已完成：**`app/services/import_post_processing.py` 已承接 `metadata / subtitle / refresh` 后置链**，`import_to_library.py` 已从 `2242` 行降到 `2094` 行。
- 当前唯一主线切到 **`app/services/import_to_library.py` 数据结构重设计 · 第 3 轮 · 抽离 approval state helper`**。
- 这一轮只允许先抽 approval 相关状态存取：pending/approve/restore/mark-executed/pending-expired/stale-check；`jobs` claim/release/complete、copy-fallback payload 和文件导入执行先不动。
- 为什么切到 services 层：`app/bot/telegram_bot.py` 已降到 `256` 行（纯 wrapper 已清空），`app/bot/private_chat_runtime.py` 当前为 `468` 行（runtime bootstrap / 开头 / 中段 / 尾段 / BT follow-up route block / execution gate preparation 都已收口）；shared runtime 层微切分已进入边际递减区，继续切分收益有限。
- 当前最大结构债转移到 services 层三座大山：`import_to_library.py` `2094` 行 / `add_to_downloader.py` `1669` 行 / `search_media.py` `1018` 行，合计 `4781` 行，占全仓 `25663` 行的 `18.6%`。当前仍只动最大的一座，另两座留待后续独立主线。
- 刚完成的上一条主线是 **`private_chat_runtime.py` execution gate preparation 边界瘦身**：execution gate + BT/PT downloader resolver 的 prepare 段已抽到 helper，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` BT follow-up route block 边界瘦身**：BT pending 预检 + processing/classification follow-up 已收成 `_handle_bt_follow_up_routes()`，当前不回退。
- 累计：shared runtime / channel 解耦已完成 `57+` 条最小直连闭环；更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退；详细闭环按 `docs/INDEX.md` §4 规则分发到各 `*_SLIMMING_LOG.md`，不在这里重述。
- 质量基线前置条件已满足：默认分支本轮复验 `.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`；仓库级 GitHub Actions `Quality` workflow 在 `push` / `pull_request` / `workflow_dispatch` 上自动跑 `make quality` + `make verify-mainline`，最近一次推送绿灯。

## User value

- post-processing 已经独立后，`import_to_library.py` 里最危险、也最值得继续收口的就是 approval 状态存取：它直接碰 `approval_record`、lease_version、executed_version 和 stale 判定。
- 先把 approval helper 抽出来，可以在不改 `jobs` 工作流和文件导入执行的前提下，缩短 confirm 主链，让“审批真相”和“文件 IO”不再继续挤在同一段代码里。
- 若 helper 抽离后被迫改变 `confirm` 文本协议或 stale/expired 语义，主线立即停住；不允许为了降行数改审批边界。

## Only do

- 只抽 approval 相关 helper，例如 `app/services/import_approval_state.py`，目标函数优先包括 `_record_pending_approval()`、`_record_import_approval()`、`_restore_pending_approval()`、`_record_executed_lease_version()`、`_resolve_pending_lease_version()`、`_find_version_stale_rejection_text()`、`_is_pending_approval_expired()`。
- `app/services/import_to_library.py` 只允许继续负责 confirm 编排、reply 决策和 helper 之间的顺序控制；approval helper 自己承接 `approval_record` 查询/写入和 fail-closed 中文日志。
- focused 验证优先跑 `tests/test_import_to_library.py -k "copy_fallback or cross_filesystem or hardlink_failure or metadata_scrape or subtitle_translate or refresh"` 与 `tests/test_import_to_library.py -k "context_lookup or context_row_corruption or raw_bt"`，必要时可补整文件回归，不新开 unrelated suite。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线；导入链详细台账继续分发到 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`。

## Do not do

- 不在这一轮触碰 `jobs` claim/release/complete 协议，不改 `_record_pending_job()`、`_claim_pending_job()`、`_restore_pending_job()`、`_mark_completed_job()`。
- 不改 `copy-fallback` pending payload 语义，不改文件导入执行函数，不改 `raw_bt` 阻断逻辑，不改 `cancel_pending_import()`。
- 不在 redesign 文档里 scope creep 到 `app/services/add_to_downloader.py` / `app/services/search_media.py`；这两个文件在当前主线完成后另起独立主线。
- 不放宽 approval、`jobs` / `job_event` / lease/version / SQLite 真相边界。
- 不新增功能、不扩协议、不顺手重写整个 `telegram_bot.py` / `app/bot/private_chat_runtime.py`。
- 不把 Telegram 渠道调度段直接平台化成新的全局 scheduler 抽象。
- 不改处理链提示协议、BT pending / approval / SQLite 真相边界。
- 不调整 `confirm` / `select` 文本协议，不改 pending add / pending import / candidate mapping / trace 日志内容语义。
- 不把 Feishu/WeCom webhook、personal WeChat、BT 订阅启动逻辑强行揉成新的"统一 sidecar 平台"。
- 不因为 shared runtime 解耦而把渠道私有 UX 重新散回各渠道各自拼接。
- 不回到 BT 页面 proof、BT dispatch 取证或 Plex 实例追查。

## Done when

当前 **`import_to_library.py` 数据结构重设计 · 第 3 轮 · 抽离 approval state helper`** 主线视为 **已收口**，需要同时满足：

1. approval helper 已承接上述 lease / approval 相关状态存取和中文 fail-closed 日志，`import_to_library.py` 不再直接持有这组大块实现；
2. `app/services/import_to_library.py` 行数从 `2094` 再下降，目标优先看 `≤ 1850`；
3. 相关 import focused 回归继续绿灯，且默认分支全量 `pytest` 没有被本轮破坏；
4. `make quality` 继续通过；
5. `docs/STATUS.md` / `docs/NEXT_STEP.md` / `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md` 已同步新的当前真相。

## After this step

1. 如果 approval helper 抽离成功，下一条主线切到 **jobs claim/release/complete helper**，再把 confirm 编排里的 job 状态迁移收口出去。
2. 如果 approval helper 抽离被证明与 confirm 编排耦合过深，下一条改走更保守的 `ImportApprovalState` dataclass + facade，不直接分裂写路径。
3. 只有在 `import_to_library.py` 的 approval / jobs 两段都收口后，才考虑触及 `add_to_downloader.py` / `search_media.py` 的结构降本主线。
