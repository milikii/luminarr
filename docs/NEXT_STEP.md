# Next step (v295)

## Current goal

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 正式宣告收工；当前阶段切到 **services 层数据结构降本**，Done 定义锁在"三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- 当前阶段第 1 条主线已完成：**`app/services/import_to_library.py` 数据结构重设计 · 第 1 轮 · 路径与特殊分支清单** 已落到 `docs/IMPORT_PIPELINE_REDESIGN.md`。
- 当前阶段第 2 条主线已完成：**`app/services/import_post_processing.py` 已承接 `metadata / subtitle / refresh` 后置链**，`import_to_library.py` 已从 `2242` 行降到 `2094` 行。
- 当前阶段第 3 条主线已完成：**`app/services/import_approval_state.py` 已承接 approval lease/version、stale-check、expiry 和目标路径回查**，`import_to_library.py` 已从 `2094` 行降到 `1827` 行。
- 当前阶段第 4 条主线已完成：**`app/services/import_job_state.py` 已承接 `jobs` pending/claim/release/complete 状态迁移**，`import_to_library.py` 已从 `1827` 行降到 `1727` 行。
- 当前阶段第 5 条主线已完成：**`app/services/import_transfer_execution.py` 已承接 copy-fallback 判定 / payload 解析 / 文件系统导入执行**，`import_to_library.py` 已从 `1727` 行降到 `1494` 行。
- 当前唯一主线切到 **`app/services/import_to_library.py` 数据结构重设计 · 第 6 轮 · 重评 `cancel_pending_import()` 是否值得继续拆`**。
- 这一轮只允许先看 `cancel_pending_import()`、`_log_cancel_pending_job_result_missing()` 和超时取消配套分支是否还能收成一个真正降低维护成本的 helper；如果剩下的只是同类 `if/elif/log` 诊断分流，就直接停止继续在 `import_to_library.py` 微切分。
- 为什么切到 services 层：`app/bot/telegram_bot.py` 已降到 `256` 行（纯 wrapper 已清空），`app/bot/private_chat_runtime.py` 当前为 `468` 行（runtime bootstrap / 开头 / 中段 / 尾段 / BT follow-up route block / execution gate preparation 都已收口）；shared runtime 层微切分已进入边际递减区，继续切分收益有限。
- 当前最大结构债仍在 services 层三座大山：`add_to_downloader.py` `1669` 行 / `import_to_library.py` `1494` 行 / `search_media.py` `1018` 行。`import_to_library.py` 已不再是按行数计算的第一大山，但它还剩最后一块高风险 confirm/cancel 链，值得只再做一次收益重评。
- 刚完成的上一条主线是 **`private_chat_runtime.py` execution gate preparation 边界瘦身**：execution gate + BT/PT downloader resolver 的 prepare 段已抽到 helper，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` BT follow-up route block 边界瘦身**：BT pending 预检 + processing/classification follow-up 已收成 `_handle_bt_follow_up_routes()`，当前不回退。
- 累计：shared runtime / channel 解耦已完成 `57+` 条最小直连闭环；更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退；详细闭环按 `docs/INDEX.md` §4 规则分发到各 `*_SLIMMING_LOG.md`，不在这里重述。
- 质量基线前置条件已满足：本轮 `make quality` 为 `24 passed`，`tests/test_import_to_library.py` 为 `142 passed`，全量 `.venv/bin/python -m pytest -q` 为 `1716 passed, 4 warnings`；真实 `/data/downloads/tr -> /data/library/movies` 硬链接 smoke 已通过。

## User value

- file-transfer helper 已经把“状态机编排”和“文件系统执行”拆开，`import_to_library.py` 现在只剩 cancel/expired cancel 这块 confirm 邻接高风险链还比较厚。
- 再做一次 `cancel_pending_import()` 收益重评，可以尽快判断 `import_to_library.py` 是继续收最后一个 helper，还是应该立刻转去更大的 `add_to_downloader.py`。
- 若下一轮只能拆出同类诊断分流而没有明确结构降本，就应该直接停住，不允许为了降行数硬拆高风险取消协议。

## Only do

- 只重评 `cancel_pending_import()` 是否还存在单一职责 helper；如果有，helper 只承接 approval cancel / pending job cancel / fail-closed 中文日志中的一整块，不得拆成多条零碎诊断支线。
- `app/services/import_to_library.py` 继续负责导入入口、confirm 编排和 helper 顺序控制；不回退已经完成的 context / approval / jobs / file-transfer helper。
- focused 验证优先跑 `tests/test_import_to_library.py -k "cancel_pending_import or expired_pending_confirm"`；只有在代码真的变更时才补 `make quality` 和全量 `pytest`。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线；导入链详细台账继续分发到 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`。

## Do not do

- 不在这一轮回退或改写 approval helper / jobs helper / file-transfer helper，不改 stale / expiry / pending lease 查询边界，也不改 `jobs` 状态迁移顺序。
- 不改 `copy-fallback` pending payload 语义，不改 `raw_bt` 阻断逻辑，不改 cancel / confirm / import 用户文本协议。
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

当前 **`import_to_library.py` 数据结构重设计 · 第 6 轮 · 重评 `cancel_pending_import()` 是否值得继续拆`** 主线视为 **已收口**，需要同时满足：

1. 已明确给出结论：`cancel_pending_import()` 要么抽出一个真正有用户价值的 helper，要么被宣告进入收益递减区；
2. 若继续拆，`import_to_library.py` 行数继续下降且不改 cancel 协议、SQLite 真相和中文 fail-closed 日志；
3. cancel 相关 focused tests 继续绿灯；
4. 若本轮有代码改动，`make quality` 和全量 `pytest` 不被破坏；
5. `docs/STATUS.md` / `docs/NEXT_STEP.md` / `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md` 已同步新的当前真相。

## After this step

1. 如果 `cancel_pending_import()` 仍有一个清晰 helper 可抽，就只做这一条最小闭环，然后停止继续在 `import_to_library.py` 微切分。
2. 如果下一轮证明这里只剩诊断分流，不再继续拆 `import_to_library.py`，直接把主线切到 `app/services/add_to_downloader.py`。
3. `search_media.py` 继续排在 `add_to_downloader.py` 之后，不提前并线。
