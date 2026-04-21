# Next step (v294)

## Current goal

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 正式宣告收工；当前阶段切到 **services 层数据结构降本**，Done 定义锁在"三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- 当前阶段第 1 条主线已完成：**`app/services/import_to_library.py` 数据结构重设计 · 第 1 轮 · 路径与特殊分支清单** 已落到 `docs/IMPORT_PIPELINE_REDESIGN.md`。
- 当前阶段第 2 条主线已完成：**`app/services/import_post_processing.py` 已承接 `metadata / subtitle / refresh` 后置链**，`import_to_library.py` 已从 `2242` 行降到 `2094` 行。
- 当前阶段第 3 条主线已完成：**`app/services/import_approval_state.py` 已承接 approval lease/version、stale-check、expiry 和目标路径回查**，`import_to_library.py` 已从 `2094` 行降到 `1827` 行。
- 当前阶段第 4 条主线已完成：**`app/services/import_job_state.py` 已承接 `jobs` pending/claim/release/complete 状态迁移**，`import_to_library.py` 已从 `1827` 行降到 `1727` 行。
- 当前唯一主线切到 **`app/services/import_to_library.py` 数据结构重设计 · 第 5 轮 · 抽离 copy-fallback / file-transfer helper`**。
- 这一轮只允许先抽 `_resolve_execution_mode()`、`_record_copy_fallback_pending()`、`_clear_pending_copy_fallback()`、`_log_copy_fallback_payload_corrupted()`，以及 `_hardlink_import()` / `_copy_import()` / `_hardlink_directory()` / `_cleanup_partial_target()` 这一组；approval helper、jobs helper 和 `cancel_pending_import()` 先不动。
- 为什么切到 services 层：`app/bot/telegram_bot.py` 已降到 `256` 行（纯 wrapper 已清空），`app/bot/private_chat_runtime.py` 当前为 `468` 行（runtime bootstrap / 开头 / 中段 / 尾段 / BT follow-up route block / execution gate preparation 都已收口）；shared runtime 层微切分已进入边际递减区，继续切分收益有限。
- 当前最大结构债转移到 services 层三座大山：`import_to_library.py` `1727` 行 / `add_to_downloader.py` `1669` 行 / `search_media.py` `1018` 行，合计 `4414` 行，占全仓 `25663` 行的 `17.2%`。当前仍只动最大的一座，另两座留待后续独立主线。
- 刚完成的上一条主线是 **`private_chat_runtime.py` execution gate preparation 边界瘦身**：execution gate + BT/PT downloader resolver 的 prepare 段已抽到 helper，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` BT follow-up route block 边界瘦身**：BT pending 预检 + processing/classification follow-up 已收成 `_handle_bt_follow_up_routes()`，当前不回退。
- 累计：shared runtime / channel 解耦已完成 `57+` 条最小直连闭环；更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退；详细闭环按 `docs/INDEX.md` §4 规则分发到各 `*_SLIMMING_LOG.md`，不在这里重述。
- 质量基线前置条件已满足：默认分支本轮复验 `.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`；仓库级 GitHub Actions `Quality` workflow 在 `push` / `pull_request` / `workflow_dispatch` 上自动跑 `make quality` + `make verify-mainline`，最近一次推送绿灯。

## User value

- approval 和 `jobs` 都已经从主文件拿走后，`import_to_library.py` 里最重的一段只剩 copy-fallback 判定和文件导入执行，这也是 confirm 主链最后一块大体积 I/O 分支。
- 先把 file-transfer helper 抽出来，可以把“状态机编排”和“文件系统执行”彻底拆开，后面再看是否值得继续压 cancel 路径或转去下一座大山。
- 若 helper 抽离后被迫改变 `confirm` / `import` 的回复文本、copy-fallback 协议或导入成功真相，主线立即停住；不允许为了降行数改文件执行边界。

## Only do

- 只抽 copy-fallback / file-transfer helper，例如 `app/services/import_transfer_execution.py`，目标函数优先包括 `_resolve_execution_mode()`、`_record_copy_fallback_pending()`、`_clear_pending_copy_fallback()`、`_log_copy_fallback_payload_corrupted()`、`_hardlink_import()`、`_copy_import()`、`_hardlink_directory()`、`_cleanup_partial_target()`。
- `app/services/import_to_library.py` 只允许继续负责 confirm 编排、reply 决策和 helper 顺序控制；file-transfer helper 自己承接 copy-fallback 判定、文件系统导入执行和中文 fail-closed 日志。
- focused 验证优先跑 `tests/test_import_to_library.py`，必要时再补全量 `pytest`；不新开 unrelated suite，不把验证范围扩到其他 service。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线；导入链详细台账继续分发到 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`。

## Do not do

- 不在这一轮回退或改写 approval helper / jobs helper，不改 stale / expiry / pending lease 查询边界，也不改 `jobs` 状态迁移顺序。
- 不改 `copy-fallback` pending payload 语义，不改 `raw_bt` 阻断逻辑，不改 `cancel_pending_import()`。
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

当前 **`import_to_library.py` 数据结构重设计 · 第 5 轮 · 抽离 copy-fallback / file-transfer helper`** 主线视为 **已收口**，需要同时满足：

1. file-transfer helper 已承接上述 copy-fallback 判定与文件导入执行，`import_to_library.py` 不再直接持有这组大块实现；
2. `app/services/import_to_library.py` 行数从 `1727` 再下降，目标优先看 `≤ 1500`；
3. `tests/test_import_to_library.py` 继续绿灯，且默认分支全量 `pytest` 没有被本轮破坏；
4. `make quality` 继续通过；
5. `docs/STATUS.md` / `docs/NEXT_STEP.md` / `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md` 已同步新的当前真相。

## After this step

1. 如果 file-transfer helper 抽离成功，下一条优先重评 `cancel_pending_import()` 是否还值得继续单拆；若收益递减，就停止继续在 `import_to_library.py` 微切分。
2. 如果 file-transfer helper 抽离被证明会牵动 reply 文本或 copy-fallback 协议，下一条改走更保守的 `ImportTransferPlan` facade，不直接把执行函数全部外提。
3. 只有在 `import_to_library.py` 的 approval / jobs / file-transfer 三段都收口后，才考虑触及 `add_to_downloader.py` / `search_media.py` 的结构降本主线。
