# Next step (v373)

## Current goal

- 当前默认分支回到 **质量硬化完成态 / 新结构债复评估**。
- 当前这一轮只服务两件事：
  - 保持刚完成的 cleanup 支持文件收口、重复 trace logger 收口、`_COMPAT_REEXPORTS` 清理、docs 归档减法、`search_media.py` / `import_to_library.py` 冻结态和 downloader adult registry 收口完成态，不回退
  - 只在出现新的 worth-it 结构债时，再进入下一个最小闭环
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
  - `app/services/workflow_trace_logger.py` 已落地；`AddToDownloaderService` 与 `ImportToLibraryService` 都已直接改用共享实现，不再保留 workflow 专属 trace logger 文件

## User value

- 当前默认分支已经把 docs 主目录历史施工文档归档完成，也把 cleanup 链支持文件、重复 trace logger 和 `_COMPAT_REEXPORTS` 清理完成；接下来最有价值的是重新挑一条新的、真正 worth-it 的结构债，而不是继续围着已完成主线打转。
- 这一步只允许对“新的结构债”做最小闭环，不碰搜索真相、下载确认协议、shared runtime 或新的展示层扩展。
- 先把“trace logger 已完成，不回头重建”固化下来，后续不会再被旧主线吸回去。

## Only do

- 只在下面两类情况里重新进入代码施工：
  - 出现新的 worth-it 结构债或明显重复代码
  - 用户显式指定新的减法主线
- 每轮仍只做一个最小闭环；同步补对应 focused tests、`docs/STATUS.md`、`docs/NEXT_STEP.md` 和相关主线文档。
- 继续保持当前 downloader / 搜索 / 导入 / 成人 BT / 验证入口已收口真相与文档一致。

## Do not do

- 不回头重建任何 `cleanup_*_support.py`、workflow trace 壳或 `_COMPAT_REEXPORTS` 兼容 tuple。
- 不在没有新证据的情况下又绕回 `search_media.py` / `import_to_library.py` / `add_to_downloader.py`。
- 不把“完成态冻结”误改成新的大扫除；没有显式主线时，不顺手扩到 shared runtime、消息展示层、`.env.example`、`AGENTS.md` 或新的 operator prompt 设计。

## Done when

当前这条 **质量硬化完成态 / 新结构债复评估** 主线满足：

1. 已明确确认 cleanup 支持文件收口、重复 trace logger 收口和 `_COMPAT_REEXPORTS` 清理都已完成。
2. `tests/test_cleanup_downloaded_source.py`、`tests/test_cleanup_docs_consistency.py`、`tests/test_adult_archive_service.py`、trace focused gate 与 `tests/test_main.py tests/test_telegram_bot.py` 仍通过。
3. `docs/STATUS.md`、`docs/NEXT_STEP.md` 对当前风险、完成态边界和下一候选结构债表述一致。

## After this step

1. 如果后续还要继续减法，优先评估新的重复代码或结构债，例如 `config.py` 重复解析逻辑。
2. 如果后续想切去用户可感知改进，再看 `docs/SEARCH_REPLY_PRESENTATION_PLAN.md`。
