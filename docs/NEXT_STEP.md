# Next step (v371)

## Current goal

- 当前唯一主线切到 **重复 trace logger 收口 / 质量硬化**。
- 当前这一轮只服务两件事：
  - 继续把 add / import 两条链里重复的 workflow trace logger 壳层收成共享实现
  - 保持刚完成的 cleanup 支持文件收口、docs 归档减法、`search_media.py` / `import_to_library.py` 冻结态和 downloader adult registry 收口完成态，不回退
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
  - cleanup 链当前已不再保留 `cleanup_*_support.py` 文件；相关逻辑已经收回 `cleanup_downloaded_source.py`、`cleanup_correlation_lookup.py` 和 `adult_archive_service.py`
  - `app/services/workflow_trace_logger.py` 已落地；`add_trace_logger.py` 已改为只承接 add workflow 常量绑定

## User value

- 当前默认分支已经把 docs 主目录历史施工文档归档完成，也把 cleanup 链的支持文件收口完成；接下来最有价值的是先清掉 add / import 两条链里明显的重复 trace logger。
- 这一步只允许对 trace logger 重复壳做最小闭环，不碰搜索真相、下载确认协议、shared runtime 或新的展示层扩展。
- 先把 trace logger 收成一套共享实现，后续再挑别的结构债时不会继续复制这种薄壳模式。

## Only do

- 只在 trace logger 这条线里动下面这些稳定边界：
  - 共享 workflow trace logger 实现
  - add/import 两条链各自的 workflow 常量绑定壳
  - 与 trace focused gate 直接相关的最小文档同步
- 每轮仍只做一个最小闭环；同步补对应 focused tests、`docs/STATUS.md`、`docs/NEXT_STEP.md` 和相关主线文档。
- 继续保持当前 downloader / 搜索 / 导入 / 成人 BT / 验证入口已收口真相与文档一致。

## Do not do

- 不回头重建任何 `cleanup_*_support.py`。
- 不在这一步顺手改 trace 之外的 add / import 协议、jobs / approval 真相或 shared runtime。
- 不把重复壳收口又扩成新的大扫除；没有显式主线时，不顺手碰 `_COMPAT_REEXPORTS`、`config.py`、消息展示层、`.env.example` 或 `AGENTS.md`。

## Done when

当前这条 **重复 trace logger 收口 / 质量硬化** 主线满足：

1. add / import 两条链不再各自保留重复的 workflow trace logger 实现，或至少共享底层实现并把重复壳压到最小。
2. `tests/test_workflow_trace_logger.py`、相关 trace focused gate 与这轮涉及的质量 gate 仍通过。
3. `docs/STATUS.md`、`docs/NEXT_STEP.md` 对当前 trace 收口方向和下一候选结构债表述一致。

## After this step

1. 如果 trace logger 线也收得差不多了，再评估 `_COMPAT_REEXPORTS` 或 `config.py` 重复解析逻辑。
2. 如果后续想切去用户可感知改进，再看 `docs/SEARCH_REPLY_PRESENTATION_PLAN.md`。
