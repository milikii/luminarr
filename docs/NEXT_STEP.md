# Next step (v368)

## Current goal

- 当前唯一主线切到 **`cleanup_*_support.py` 代码碎片收口 / 质量硬化**。
- 当前这一轮只服务两件事：
  - 继续把 cleanup 链里只服务单点的微型 helper 往主文件或更粗的稳定模块收回
  - 保持刚完成的 docs 归档减法、`search_media.py` / `import_to_library.py` 冻结态和 downloader adult registry 收口完成态，不回退
- 已完成态保持，不回退：
  - `Makefile` 公开验证入口已收口：`verify-mainline` 当前改成 4 个分组 target 汇总入口，cleanup 公开入口收敛到 `test-cleanup-smoke` / `test-cleanup` / `test-cleanup-docs-gate` / `test-cleanup-window`
  - `docs/OPERATOR_RUNBOOK.md` / `docs/GETTING_STARTED.md` 当前已去掉过时主线残留和重复入口
  - `docs/` 主目录历史施工文档已归档到 `archive/docs/`
  - 成人 BT 站点优先、历史账本、只读补全、归档与保留期清理
  - 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态
  - `app/services/add_adult_registry_state.py` 已承接 adult pending / downloading 状态写入；`add_to_downloader.py` 当前 `582` 行，只剩 proof-like wrapper
  - `search_media.py` 当前 `288` 行，歧义澄清 / media-BT 排序 / batch preview 页面支持 helper 已抽到独立模块
  - `import_to_library.py` 当前 `590` 行，confirmed media identity 回查已抽到 `app/services/import_confirmed_media_identity.py`，focused gate + pyflakes 复评估已确认当前没有 worth-it 闭环
  - `app/bot/private_chat_runtime.py` 当前 `476` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退
  - `cleanup_correlation_lookup.py` 已收回 `cleanup_correlation_event_support.py` / `cleanup_correlation_flow_support.py` / `cleanup_correlation_result_support.py` 三个微文件；`cleanup_downloaded_source.py` 已收回 `cleanup_inspect_flow_support.py` / `cleanup_path_guard_support.py` / `cleanup_query_support.py` / `cleanup_event_support.py` 四个薄壳；`cleanup_flow_support.py` 已收回 `cleanup_blocked_support.py` / `cleanup_execution_support.py` / `cleanup_follow_up_support.py` / `cleanup_inspect_render_support.py` 四个薄壳；`cleanup_logging_support.py` 已收回 `cleanup_correlation_logging_support.py`

## User value

- 当前默认分支已经把 docs 主目录历史施工文档归档完成，接下来最有价值的是继续压 cleanup 链里的微型 helper，直接减少碎片文件数。
- 这一步只允许对 cleanup 链做最小闭环，不碰搜索真相、下载确认协议、shared runtime 或新的展示层扩展。
- 先把 cleanup 这条碎片链压薄，后续再切别的主线时不会被一堆只服务单点的 helper 吸回去。

## Only do

- 只在 cleanup 链里动下面这些稳定边界：
  - 能直接回收的单点 helper
  - 能合并进现有主文件的薄壳
  - 能减少碎片文件数的稳定职责收口
- 每轮仍只做一个最小闭环；同步补对应 focused tests、`docs/STATUS.md`、`docs/NEXT_STEP.md` 和相关主线文档。
- 继续保持当前 downloader / 搜索 / 导入 / 成人 BT / 验证入口已收口真相与文档一致。

## Do not do

- 不把 cleanup 收口又绕回 `search_media.py` / `import_to_library.py` / `add_to_downloader.py`。
- 不在没有新证据的情况下把薄壳拆成更多薄壳；优先合并，不要机械重命名。
- 不把 cleanup 主线误改成新的大扫除；没有显式主线时，不顺手扩到 shared runtime、消息展示层、`.env.example`、`AGENTS.md` 或新的 operator prompt 设计。

## Done when

当前这条 **`cleanup_*_support.py` 代码碎片收口 / 质量硬化** 主线满足：

1. `cleanup_*_support.py` 数量继续下降，当前剩余数量以 `6` 为基线，且优先通过合并而不是新拆薄壳来收口。
2. `tests/test_cleanup_downloaded_source.py` 和 `tests/test_cleanup_docs_consistency.py` 仍通过。
3. `docs/STATUS.md`、`docs/NEXT_STEP.md` 和 cleanup 相关文档对当前收口方向和剩余碎片表述一致。

## After this step

1. 如果 cleanup 链也收得差不多了，再评估是否切去新的消息展示热点，统一蓝图继续看 `docs/SEARCH_REPLY_PRESENTATION_PLAN.md`。
2. 如果后续仍想继续压文档/配置负担，再单开 `AGENTS.md` / `.env.example` 入口瘦身主线，不和 cleanup 主线混做。
