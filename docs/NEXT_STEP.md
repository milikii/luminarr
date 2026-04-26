# Next step (v365)

## Current goal

- 当前唯一主线切到 **历史 docs 归档减法 / 质量硬化**。
- 当前这一轮只服务两件事：
  - 把已完成主线的 `*_PLAN.md` / `*_SLIMMING_LOG.md` / 历史风险日志移出 `docs/` 主目录，只保留当前入口、当前真相、长期边界和仍活跃的候选蓝图
  - 同步收紧 `README.md`、`docs/HUMAN_START_HERE.md`、`docs/OPERATOR_RUNBOOK.md`、`docs/INDEX.md` 和 docs gate，避免后续接手继续被历史文档吸回去
- 已完成态保持，不回退：
  - `Makefile` 公开验证入口已收口：`verify-mainline` 当前改成 4 个分组 target 汇总入口，cleanup 公开入口当前收敛到 `test-cleanup-smoke` / `test-cleanup` / `test-cleanup-docs-gate` / `test-cleanup-window`
  - `docs/OPERATOR_RUNBOOK.md` / `docs/GETTING_STARTED.md` 当前已去掉过时主线残留和重复入口
  - 成人 BT 站点优先、历史账本、只读补全、归档与保留期清理
  - 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态
  - `app/services/add_adult_registry_state.py` 已承接 adult pending / downloading 状态写入；`add_to_downloader.py` 当前 `582` 行，只剩 proof-like wrapper
  - `search_media.py` 当前 `288` 行，歧义澄清 / media-BT 排序 / batch preview 页面支持 helper 已抽到独立模块
  - `import_to_library.py` 当前 `590` 行，confirmed media identity 回查已抽到 `app/services/import_confirmed_media_identity.py`，focused gate + pyflakes 复评估已确认当前没有 worth-it 闭环
  - `app/bot/private_chat_runtime.py` 当前 `476` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退
  - 当前文档减法目标不是再拆业务代码，而是把已完成主线台账移到 `archive/docs/`，收回活跃 `docs/` 目录

## User value

- 当前默认分支已经把搜索和导入两条热点线都收回到 proof-like orchestration；现在最有价值的是把主 `docs/` 目录里的历史施工文档清掉，让入口只剩当前真相。
- 这一步只动文档、归档路径和 docs gate，不碰搜索真相、下载确认协议、shared runtime 或新的展示层扩展。
- 文档入口减法做完后，后续不管切消息展示体验还是继续压文档负担，都不会再被旧 `*_PLAN.md` / `*_SLIMMING_LOG.md` 吸回去。

## Only do

- 只做下面三类文档减法：
  - 已完成主线台账迁到 `archive/docs/`
  - 活跃入口文档改成只指向当前真相或归档位置
  - docs gate 改成校验“当前入口 + 归档位置”，不再逐份绑死历史台账
- 每轮仍只做一个最小闭环；同步补对应 docs gate、`docs/STATUS.md`、`docs/NEXT_STEP.md` 和相关入口文档。
- 继续保持当前 downloader / 搜索 / 导入 / 成人 BT / 验证入口已收口真相与文档一致。

## Do not do

- 不为把 `import_to_library.py`、`search_media.py`、`add_to_downloader.py` 压到更小数字而继续机械拆 wrapper。
- 不在这一步改业务代码、协议、SQLite 真相边界或 shared runtime。
- 不把 archive 迁移顺手扩成新的大扫除；没有明确证据时，不顺手删当前入口文档、当前候选蓝图、`.env.example`、`AGENTS.md` 或运行说明。

## Done when

当前这条 **历史 docs 归档减法 / 质量硬化** 主线满足：

1. 主 `docs/` 目录只保留当前入口、当前真相、长期边界和仍活跃的候选蓝图；已完成主线台账迁到 `archive/docs/`。
2. `tests/test_cleanup_docs_consistency.py` 与相关 docs gate 通过。
3. `docs/STATUS.md`、`docs/NEXT_STEP.md`、`docs/INDEX.md` 对当前主线、归档位置和后续候选线程表述一致。

## After this step

1. 如果这一轮完成后仍有文档减法价值，优先继续收入口漂移、历史计划口径和根目录冗余，而不是回头重拆业务代码。
2. 如果文档减法也完成，再评估是否切到新的消息展示热点，统一蓝图继续看 `docs/SEARCH_REPLY_PRESENTATION_PLAN.md`。
