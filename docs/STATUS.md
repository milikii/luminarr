# Current status (v496)

## Current mainline

- **质量硬化** 当前保持完成态，不回退。
- 当前默认分支主线的 **`config.py` 重复解析逻辑收口 / 质量硬化** 已完成：`RAW_BT_DESTINATIONS`、`ADULT_ARCHIVE_DESTINATIONS`、`DOWNLOADER_INSTANCES` 已共用分条/分段解析 helper，不改 settings 语义。
- `Makefile` 公开验证入口与操作者入口文档已收口：`verify-mainline` 现在是 4 个分组 target 汇总入口，cleanup 公开入口收敛到 `test-cleanup-smoke` / `test-cleanup` / `test-cleanup-docs-gate` / `test-cleanup-window`，`docs/OPERATOR_RUNBOOK.md` / `docs/GETTING_STARTED.md` 已去掉过时残留。
- 成人 BT / qB / Transmission 当前真相继续保持：exact-id read-only helper 只补展示字段，helper-only 字段不进 truth，归档 / 保留期清理继续可用，真实归档 smoke 通过。
- `qB` 导入源解析继续优先真实 `content_path`；`DOWNLOADER_INSTANCES` 的 `dispatch_download_dir` 与宿主机导入路径保持分离；路由层继续优先任务真相里的 host `download_dir`。
- `app/services/add_adult_registry_state.py` 已统一 adult pending / downloading 状态写入；`add_to_downloader.py` `582` 行只剩 proof-like wrapper，可先停手不回退。
- `search_media.py` 已降到 `288` 行，歧义澄清 / media-BT 排序 / batch preview 页面支持 helper 都已抽出；`import_to_library.py` 当前 `590` 行，经 focused gate + pyflakes 复核后继续保持 proof-like orchestration 冻结态。
- `cleanup_correlation_lookup.py` 已收回 task identity、correlation lookup、correlation logging 全部薄壳；`cleanup_downloaded_source.py` 已收回 inspect / path guard / query / event / flow / blocked / execution / follow-up / seed-guard / logging / 资产删除 全部薄壳；`adult_archive_service.py` 也不再依赖 cleanup 资产删除 helper。`cleanup_*_support.py` 当前为 `0` 个。
- `app/services/workflow_trace_logger.py` 已落地为共享 workflow trace logger；`AddToDownloaderService` 与 `ImportToLibraryService` 都已直接改用共享实现，不再保留 workflow 专属 trace logger 文件。
- `app/main.py` 里的 downloader client 本地死壳已删掉；`app/main.py` 与 `app/bot/telegram_bot.py` 的 `_COMPAT_REEXPORTS` 也已删除；`app/bot/personal_wechat_login.py` 与 `app/bot/personal_wechat_text.py` 的无消费者 `__all__` 纯导出列表继续保持删除态，`app/db/__init__.py` 的死 re-export 已清掉，`app/bot/telegram_bot.py` 当前改为显式公共 `__all__` 边界以维持 pyflakes 绿灯，功能测试继续通过，不影响现有直接导入形状。
- `app/config.py` 当前 `461` 行；`RAW_BT_DESTINATIONS`、`ADULT_ARCHIVE_DESTINATIONS`、`DOWNLOADER_INSTANCES` 已共用分条/分段解析 helper，`RAW_BT_DESTINATIONS` / `ADULT_ARCHIVE_DESTINATIONS` 现已共用 labelled destination record factory，base URL 现在也统一走 shared normalization helper，当前不再继续在这条边界上做重复壳。
- `app/downloader_route_lookup.py` 当前 `369` 行；task/downloader 日志上下文、payload JSON 解析收口、lookup route/client 抛错、status/remove 的 client-only 序幕、import host download_dir 回填和 import source `download_dir` 重建都已收成共享 helper；本轮继续把 downloader instance strip + lookup、host download_dir fallback 都合成共享解析 helper，并把 task route / dispatch 日志直接落到共享打印入口，`_log_*` 当前已归零，不改错误文本、路由语义或导入/状态协议。
- `docs/TEST_ENV.md` 与 `tmp_tests/` 已按“彻底不用后删”退出活跃仓库真相；当前活跃 `docs/` 根目录 Markdown 为 `15` 个。

## Current health

- 代码热点线当前都已经回到 proof-like orchestration；cleanup 支持文件、重复 trace logger、`_COMPAT_REEXPORTS` 清理、无消费者 `__all__` 清理、`config.py` 重复解析逻辑、`app/main.py` 残余 downloader client 本地死壳和 route helper 侧的重复上下文/抛错/回填壳都已完成，这轮主风险继续落在 `downloader_route_lookup.py` 是否还存在值得继续收的“只被单点消费的薄壳”，当前已继续压薄 payload corruption 与 host download_dir fallback。
- 当前归档迁移、cleanup 收口、trace logger 收口、`_COMPAT_REEXPORTS` 清理、无消费者 `__all__` 清理、`config.py` 收口、`app/main.py` 残余下载器本地死壳清理和 `tests/test_main.py` 对 route helper 的错误边界依赖修正都已落地；当前最小风险仍在 `downloader_route_lookup.py`，但应继续沿小 helper/死壳减法推进，不要回头重建旧壳层。
- `tests/test_main.py` 里 downloader route helper 相关断言当前已直接 import `app.downloader_route_lookup` 真实边界，不再借 `app.main` 中转。

## Later candidate line

- 当前 cleanup 支持文件收口、重复 trace logger 收口、`_COMPAT_REEXPORTS` 清理和 `config.py` 重复解析逻辑都已完成；当前更保守候选仍是 `downloader_route_lookup.py` 剩余单消费者薄壳/重复 helper，再之后才是用户可感知改进。
- 这条后续候选主线固定为 `Telegram-first`：先做 Telegram richer reply，Feishu / personal WeChat / WeCom 首阶段先保留共享文本降级，不改 shared runtime / approval / dispatch 真相。
- 成人 BT 图片目标当前记为“尽量全量带图”，但实施分阶段；拿不到稳定图源时明确降级为纯文本。

## Latest verification

- `make quality`：`32 passed, 0 skipped`
- `make verify-mainline`：当前完成态保持通过
- focused pytest：
  - `tests/test_add_execution_follow_up.py tests/test_add_to_downloader.py tests/test_private_chat_confirm_runtime.py`：`125 passed`
  - `tests/test_search_ambiguity_helper.py tests/test_search_media.py -k "ambiguous or clarification"`：`15 passed, 173 deselected`
  - `tests/test_search_media_bt_ordering.py tests/test_search_media.py -k "orders_media_bt_candidates or fallback_query or quality_from_title"`：`6 passed, 183 deselected`
- `tests/test_search_media_batch_preview_support.py tests/test_search_media.py -k "batch_preview or page_url or unsupported"`：`70 passed, 118 deselected`
- `tests/test_import_to_library.py -k "context_lookup or context_row_corruption or raw_bt or copy_fallback or cross_filesystem or hardlink_failure or metadata_scrape or subtitle_translate or refresh"`：`30 passed, 119 deselected`
- `tests/test_cleanup_downloaded_source.py tests/test_cleanup_docs_consistency.py tests/test_adult_archive_service.py`：`57 passed`
- `tests/test_workflow_trace_logger.py tests/test_trace_logging.py tests/test_add_to_downloader.py -k "trace_log"`：`5 passed, 111 deselected`
- `tests/test_main.py tests/test_telegram_bot.py tests/test_personal_wechat_login.py tests/test_personal_wechat_text.py`：`255 passed`
- `tests/test_downloader_route_lookup.py tests/test_main.py tests/test_telegram_bot.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_runtime_adapter.py`：`399 passed`
- `tests/test_config.py`：`34 passed`
- `tests/test_downloader_route_lookup.py tests/test_main.py`：`30 passed`
- `tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py`：`26 passed`
- 本轮 focused gate：
  - `tests/test_downloader_route_lookup.py tests/test_main.py`：`32 passed`
- 真实 smoke 保持通过态，本轮未改下载器 / 归档协议。

## Current biggest risk

- 当前 biggest risk 已不再是 cleanup 支持文件、trace logger 重复壳、`_COMPAT_REEXPORTS` 或 `config.py`；下一轮如果继续减法，应沿 `downloader_route_lookup.py` 的剩余单消费者 helper / 死壳推进，而不是把范围扩成整份路由系统重写。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

这轮 `downloader_route_lookup.py` 的 task/downloader 日志上下文、payload 解析/读取、lookup 抛错、status/remove 路由序幕和 import download_dir 回填壳已继续收口。若继续，默认不要回头重建 cleanup 薄壳、workflow trace 壳或兼容 tuple；优先挑 `downloader_route_lookup.py` 剩余单消费者 helper 或 route 死壳做一个更小闭环。
```
