# Next step (v294)

## Current goal

- **质量硬化** 阶段已按 `docs/DECISIONS.md` D-039 正式宣告收工；当前阶段切到 **services 层数据结构降本**，Done 定义锁在"三座大山各 `≤ 600` 行 + focused tests 不跌 + CI 绿灯"。
- 当前阶段第 1 条主线切到 **`app/services/import_to_library.py` 数据结构重设计 · 第 1 轮 · 路径与特殊分支清单**。
- 这一轮 **不改业务代码**，只新建 `docs/IMPORT_PIPELINE_REDESIGN.md`：把 `import_to_library.py` 当前 `2242` 行的所有入口路径、特殊分支 grep 计数和候选重设计数据结构草图固化下来，作为后续结构降本主线的可测量基线。
- 为什么切到 services 层：`app/bot/telegram_bot.py` 已降到 `256` 行（纯 wrapper 已清空），`app/bot/private_chat_runtime.py` 当前为 `468` 行（runtime bootstrap / 开头 / 中段 / 尾段 / BT follow-up route block / execution gate preparation 都已收口）；shared runtime 层微切分已进入边际递减区，继续切分收益有限。
- 当前最大结构债转移到 services 层三座大山：`import_to_library.py` `2242` 行 / `add_to_downloader.py` `1669` 行 / `search_media.py` `1018` 行，合计 `4929` 行，占全仓 `25663` 行的 `19%`。本轮只先动最大的一座，另两座留待后续独立主线。
- 刚完成的上一条主线是 **`private_chat_runtime.py` execution gate preparation 边界瘦身**：execution gate + BT/PT downloader resolver 的 prepare 段已抽到 helper，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` BT follow-up route block 边界瘦身**：BT pending 预检 + processing/classification follow-up 已收成 `_handle_bt_follow_up_routes()`，当前不回退。
- 累计：shared runtime / channel 解耦已完成 `57+` 条最小直连闭环；更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退；详细闭环按 `docs/INDEX.md` §4 规则分发到各 `*_SLIMMING_LOG.md`，不在这里重述。
- 质量基线前置条件已满足：默认分支本轮复验 `.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`；仓库级 GitHub Actions `Quality` workflow 在 `push` / `pull_request` / `workflow_dispatch` 上自动跑 `make quality` + `make verify-mainline`，最近一次推送绿灯。

## User value

- `import_to_library.py` 是全仓最大单文件，其内部分支密度直接决定未来每次改动的脆弱性；先固化一份路径 + 分支清单，可以让后续每条结构降本闭环都有可测量的前后对比（行数 / 分支数 / 路径覆盖）。
- 第 1 轮只产出诊断文档、不动代码，可在默认分支稳绿前提下完成，不引入任何回归风险。
- 若 redesign 草图评估后判定不可行，主线立即撤回到 shared runtime 热点的下一条保守闭环；不允许在没有路径清单的情况下直接动 `import_to_library.py` 业务代码。

## Only do

- 只新建 `docs/IMPORT_PIPELINE_REDESIGN.md`，内容必须包含以下 3 节，且每节都要给出可复现的命令或数值：
  1. **入口路径清单**：列出所有进入 `import_to_library.py` 的调用点（含调用文件路径 / 函数名 / 进入分支）。
  2. **特殊分支 grep 计数**：给出 `grep -c "if " app/services/import_to_library.py`、`grep -c "elif " app/services/import_to_library.py`、`grep -c "except " app/services/import_to_library.py` 三个数值基线，以及主要分支的英文标签分类。
  3. **候选数据结构草图**：至少一版 `ImportRequest` + pipeline step 的 dataclass / protocol 草图，只画结构，不写实现；指出哪些当前特殊分支在新结构下会"自然消失"。
- 如果 redesign 草图评估后判定不可行，在同一份文档末尾追加 **主线撤回** 段，写清楚撤回原因（包括：哪条特殊分支无法归一、哪段 I/O 副作用无法拆 pipeline），并提出下一条保守主线候选。
- 保持现有 parser / routing / approval / SQLite 真相边界不变，不新增用户可感知功能，不改渠道外部协议。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线；后续每条结构降本闭环的详细台账分发到 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`。

## Do not do

- 不在这一轮修改 `app/services/import_to_library.py` / 相关测试 / 任何业务代码。
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

当前 **`import_to_library.py` 数据结构重设计 · 第 1 轮** 主线视为 **已收口**，满足以下任一条即可：

1. `docs/IMPORT_PIPELINE_REDESIGN.md` 已新建并包含上述 3 节：入口路径清单、特殊分支 grep 计数（至少 `if ` / `elif ` / `except ` 三个数值）、pipeline 草图；
2. redesign 文档末尾已给出 **主线撤回** 段，写清撤回原因并提出下一条保守主线候选；
3. 默认分支全量 pytest 继续保持绿灯（`.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped` 或更多），本轮没有动业务代码所以回归风险为零；
4. `make quality` / `make verify-mainline` 继续通过，GitHub Actions `Quality` workflow 本轮推送绿灯；
5. 文档继续保持分层一致，`STATUS.md` 只写当前快照，`NEXT_STEP.md` 只写当前唯一主线。

## After this step

1. 如果 redesign 文档给出了可执行的 pipeline 草图，下一条主线切到 **`import_to_library.py` 第一个可抽 pipeline step 的最小实现**，目标是让主文件行数首次下降（例如 `2242` → `≤ 1900`），并补对应 focused tests 到 `verify-mainline`。
2. 如果 redesign 文档判定主线撤回，下一条切回 shared runtime 热点的保守瘦身（`private_chat_runtime.py` 剩余段落 / adapter 入口 / focused gate 缺口任选其一），不允许悬空。
3. 只有在 `import_to_library.py` 重设计 / 撤回结论已明确、且当前主线 Done 之后，才考虑触及 `add_to_downloader.py` / `search_media.py` 的结构降本主线。
