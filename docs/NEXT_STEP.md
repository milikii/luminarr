# Next step (v362)

## Current goal

- 当前唯一主线切回 **`add_to_downloader.py` confirm wrapper 收口 / 质量硬化**。
- 这一轮只服务两件事：
  - 收 `app/services/add_to_downloader.py` 里仍堆在壳文件里的 confirm / pending wrapper、成人 pending 记录壳或 trace glue
  - 保持刚完成的 `Makefile` 公开验证入口收口和操作者文档瘦身完成态，不回退
- 已完成态保持，不回退：
  - `Makefile` 公开验证入口已收口：`verify-mainline` 当前改成 4 个分组 target 汇总入口，cleanup 公开入口当前收敛到 `test-cleanup-smoke` / `test-cleanup` / `test-cleanup-docs-gate` / `test-cleanup-window`
  - `docs/OPERATOR_RUNBOOK.md` / `docs/GETTING_STARTED.md` 当前已去掉过时主线残留和重复入口
  - 成人 BT 站点优先、历史账本、只读补全、归档与保留期清理
  - 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态
  - `search_media.py` 当前 `628` 行，BT 只读展示逻辑已抽到 `app/services/bt_read_only_display.py`
  - `import_to_library.py` 当前 `590` 行，confirmed media identity 回查已抽到 `app/services/import_confirmed_media_identity.py`
  - `app/bot/private_chat_runtime.py` 当前 `476` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退
- 这条主线的详细蓝图统一看 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`。

## User value

- 继续把 downloader confirm 壳文件收回去，后续再修下载待确认 / confirm 链路时，不会继续把所有小改动堆回同一个热点文件。
- 这一步只动 wrapper / 壳层和 focused tests，不碰 approval / lease / confirm / downloader dispatch 真相边界。
- 入口文档和公开验证命令已经收口，这一步可以重新把精力放回代码热点，而不是继续在人机入口上打转。

## Only do

- 只收 `add_to_downloader.py` 当前仍直连的稳定壳层：
  - pending / approval / job wrapper
  - 成人 pending 记录壳
  - trace glue
- 每轮只做一个最小闭环；同步补对应 focused tests、`docs/STATUS.md`、`docs/NEXT_STEP.md` 和 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`。
- 继续保持当前搜索 / 导入 / 成人 BT / 验证入口已收口真相与文档一致。

## Do not do

- 不为降行数而继续机械拆 wrapper；只有稳定职责边界才允许抽走。
- 不在这一步改 approval / lease / version / confirm / recovery / downloader dispatch / import 协议。
- 不在这一步切回 `search_media.py`、`import_to_library.py`、消息展示体验层或新的文档入口瘦身主线。
- 不顺手扩到 `.env.example`、`AGENTS.md` 或新的 operator prompt 设计。

## Done when

当前这条 **`add_to_downloader.py` confirm wrapper 收口 / 质量硬化** 主线满足：

1. `add_to_downloader.py` 至少再抽走一组稳定 wrapper / 壳层职责，或让壳文件职责明显更单一。
2. `tests/test_add_execution_follow_up.py`、`tests/test_add_to_downloader.py`、`tests/test_private_chat_confirm_runtime.py` 与这轮涉及的质量 gate 均通过。
3. `docs/STATUS.md`、`docs/NEXT_STEP.md`、`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md` 对当前风险和下一线程表述一致。

## After this step

1. 如果 `add_to_downloader.py` 再收一轮后仍只剩 proof-like wrapper，优先评估是否该停手并切去新的热点文件。
2. 如果后续仍想继续压文档/配置负担，再单开 `AGENTS.md` / `.env.example` 入口瘦身主线，不和 downloader 主线混做。
