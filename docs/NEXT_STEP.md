# Next step (v294)

## Current goal

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 正式宣告收工；当前阶段切到 **services 层数据结构降本**，Done 定义锁在"三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- 当前阶段第 1 条主线已完成：**`app/services/import_to_library.py` 数据结构重设计 · 第 1 轮 · 路径与特殊分支清单** 已落到 `docs/IMPORT_PIPELINE_REDESIGN.md`。
- 当前唯一主线切到 **`app/services/import_to_library.py` 数据结构重设计 · 第 2 轮 · 抽离 post-import side-effect pipeline`**。
- 这一轮开始真正动代码，但只允许先抽 `metadata / subtitle / refresh` 这一段后置链；approval、`jobs`、lease/version、copy-fallback pending 真相边界先不动。
- 为什么切到 services 层：`app/bot/telegram_bot.py` 已降到 `256` 行（纯 wrapper 已清空），`app/bot/private_chat_runtime.py` 当前为 `468` 行（runtime bootstrap / 开头 / 中段 / 尾段 / BT follow-up route block / execution gate preparation 都已收口）；shared runtime 层微切分已进入边际递减区，继续切分收益有限。
- 当前最大结构债转移到 services 层三座大山：`import_to_library.py` `2242` 行 / `add_to_downloader.py` `1669` 行 / `search_media.py` `1018` 行，合计 `4929` 行，占全仓 `25663` 行的 `19%`。当前仍只动最大的一座，另两座留待后续独立主线。
- 刚完成的上一条主线是 **`private_chat_runtime.py` execution gate preparation 边界瘦身**：execution gate + BT/PT downloader resolver 的 prepare 段已抽到 helper，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` BT follow-up route block 边界瘦身**：BT pending 预检 + processing/classification follow-up 已收成 `_handle_bt_follow_up_routes()`，当前不回退。
- 累计：shared runtime / channel 解耦已完成 `57+` 条最小直连闭环；更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退；详细闭环按 `docs/INDEX.md` §4 规则分发到各 `*_SLIMMING_LOG.md`，不在这里重述。
- 质量基线前置条件已满足：默认分支本轮复验 `.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`；仓库级 GitHub Actions `Quality` workflow 在 `push` / `pull_request` / `workflow_dispatch` 上自动跑 `make quality` + `make verify-mainline`，最近一次推送绿灯。

## User value

- `docs/IMPORT_PIPELINE_REDESIGN.md` 已证明第一段最适合落地的不是 approval 状态机，而是 `post_import_side_effects`：它只吃 `task identity + target_path + optional hooks`，独立性最高，最适合作为第一个 pipeline step。
- 先把 `metadata / subtitle / refresh` 抽成 helper，可以在不碰 SQLite 真相和审批协议的前提下，先让 `import_to_library.py` 真正掉一段体积，降低后续改动时的阅读成本和回归面。
- 若这一步抽离后发现 reply/event 协议被迫变化，主线立即停住并回退到更保守的 helper 粒度；不允许为了降行数顺手改对外文本协议。

## Only do

- 只抽 `metadata / subtitle / refresh` 这一段后置链到新 helper，例如 `app/services/import_post_processing.py`；helper 只接收已完成导入后的 identity / target / hook 依赖，不重做 approval 或 jobs 查询。
- `app/services/import_to_library.py` 只允许把这条后置链的输入准备好，再调用 helper 并消费结果；`import.succeeded` 事件、中文日志、reply 文本语义保持不变。
- focused 验证只围绕 `tests/test_import_to_library.py -k "metadata_scrape or subtitle_translate or refresh"` 和相关 docs/quality 入口补强；如 helper 抽离需要少量测试重排，可以改同文件内测试，但不新开 unrelated suite。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线；导入链详细台账继续分发到 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`。

## Do not do

- 不在这一轮触碰 `confirm_import_by_task_ref()` 里的 approval 状态机、lease/version 竞争、`jobs` claim/release/complete 协议。
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

当前 **`import_to_library.py` 数据结构重设计 · 第 2 轮 · 抽离 post-import side-effect pipeline`** 主线视为 **已收口**，需要同时满足：

1. `app/services/import_post_processing.py`（或等价 helper）已承接 `metadata / subtitle / refresh` 后置链，且 `import_to_library.py` 不再直接持有该段大块执行细节；
2. `app/services/import_to_library.py` 行数从 `2242` 降到 `< 2242`，目标优先看 `≤ 2100`；
3. `tests/test_import_to_library.py -k "metadata_scrape or subtitle_translate or refresh"` 继续绿灯；
4. `make quality` 继续通过，且默认分支全量回归没有被本轮破坏；
5. `docs/STATUS.md` / `docs/NEXT_STEP.md` / `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md` 已同步到新的当前真相。

## After this step

1. 如果 `post_import_side_effects` 抽离成功，下一条主线切到 **approval / jobs 状态存取 helper**，目标是把 `_record_pending_approval()`、`_record_import_approval()`、`_restore_pending_approval()`、`_record_executed_lease_version()`、`_record_pending_job()` 这一组从主文件挪走。
2. 如果这一步抽离被证明会牵动 reply/event 协议，下一条改走更保守的 `ImportPostProcessContext` 数据结构先行，不强拆执行 helper。
3. 只有在 `import_to_library.py` 的 pipeline 首段已经成功落地后，才考虑触及 `add_to_downloader.py` / `search_media.py` 的结构降本主线。
