# Next step (v362)

## Current goal

- 当前唯一主线切到 **`import_to_library.py` worth-it 复评估 / 质量硬化**。
- 这一轮只服务两件事：
  - 只在 `app/services/import_to_library.py` 出现明确 focused gate 缺口或新的失败边界时，收一个最小闭环
  - 保持刚完成的 `search_media.py` helper 收口和 downloader adult registry helper 收口完成态，不回退
- 已完成态保持，不回退：
  - `Makefile` 公开验证入口已收口：`verify-mainline` 当前改成 4 个分组 target 汇总入口，cleanup 公开入口当前收敛到 `test-cleanup-smoke` / `test-cleanup` / `test-cleanup-docs-gate` / `test-cleanup-window`
  - `docs/OPERATOR_RUNBOOK.md` / `docs/GETTING_STARTED.md` 当前已去掉过时主线残留和重复入口
  - 成人 BT 站点优先、历史账本、只读补全、归档与保留期清理
  - 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态
  - `app/services/add_adult_registry_state.py` 已承接 adult pending / downloading 状态写入；`add_to_downloader.py` 当前 `582` 行，只剩 proof-like wrapper
  - `search_media.py` 当前 `288` 行，歧义澄清 / media-BT 排序 / batch preview 页面支持 helper 已抽到独立模块
  - `import_to_library.py` 当前 `590` 行，confirmed media identity 回查已抽到 `app/services/import_confirmed_media_identity.py`
  - `app/bot/private_chat_runtime.py` 当前 `476` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退
  - 这条主线的详细蓝图统一看 `docs/SEARCH_MEDIA_SLIMMING_LOG.md`。

## User value

- 当前默认分支已经把搜索热点文件收回到编排层；下一步只有在导入链确实还存在 focused gate 价值时才值得继续动，避免为了数字重回机械拆壳。
- 这一步只动 import focused gate / failure boundary 和对应测试，不碰搜索真相、下载确认协议或新的展示层扩展。
- downloader / search 两条热点线都已经到完成态，这一步优先判断“还值不值得动”而不是默认继续拆。

## Only do

- 只在下面两类情况里动 `import_to_library.py`：
  - focused gate 有明确缺口
  - 新的失败边界已经能被复现或已有回归证据
- 每轮只做一个最小闭环；同步补对应 focused tests、`docs/STATUS.md`、`docs/NEXT_STEP.md` 和相关 import 文档。
- 继续保持当前 downloader / 搜索 / 成人 BT / 验证入口已收口真相与文档一致。

## Do not do

- 不为把 `import_to_library.py` 压到更小数字而继续机械拆 wrapper。
- 不在这一步改搜索真相、下载确认协议、shared runtime、消息展示层或新的入口文档设计。
- 不顺手回头继续拆已经进入 proof-like wrapper 阶段的 `search_media.py` / `add_to_downloader.py`。
- 不顺手扩到 `.env.example`、`AGENTS.md` 或新的 operator prompt 设计。

## Done when

当前这条 **`import_to_library.py` worth-it 复评估 / 质量硬化** 主线满足：

1. 明确找到一组值得动的 import focused gate / failure boundary，并完成一个最小闭环；或明确确认当前没有 worth-it 闭环，继续保持冻结。
2. `tests/test_import_to_library.py` 的相关 focused gate 与这轮涉及的质量 gate 均通过。
3. `docs/STATUS.md`、`docs/NEXT_STEP.md` 和相关 import 文档对当前风险和下一线程表述一致。

## After this step

1. 如果 import 线也确认没有 worth-it 闭环，再评估是否切去新的消息展示热点或继续保持质量硬化完成态。
2. 如果后续仍想继续压文档/配置负担，再单开 `AGENTS.md` / `.env.example` 入口瘦身主线，不和 import 主线混做。
