# Current status (v489)

## Current mainline

- **质量硬化** 当前保持完成态，不回退。
- 当前默认分支主线的 **`cleanup_*_support.py` 代码碎片收口 / 质量硬化** 已完成；cleanup 链当前已不再保留 `*_support.py` 文件。若继续，下一条更保守候选应切去新的重复代码或结构债，不回头重建 cleanup 薄壳。
- `Makefile` 公开验证入口与操作者入口文档已收口：`verify-mainline` 现在是 4 个分组 target 汇总入口，cleanup 公开入口收敛到 `test-cleanup-smoke` / `test-cleanup` / `test-cleanup-docs-gate` / `test-cleanup-window`，`docs/OPERATOR_RUNBOOK.md` / `docs/GETTING_STARTED.md` 已去掉过时残留。
- 成人 BT / qB / Transmission 当前真相继续保持：exact-id read-only helper 只补展示字段，helper-only 字段不进 truth，归档 / 保留期清理继续可用，真实归档 smoke 通过。
- `qB` 导入源解析继续优先真实 `content_path`；`DOWNLOADER_INSTANCES` 的 `dispatch_download_dir` 与宿主机导入路径保持分离；路由层继续优先任务真相里的 host `download_dir`。
- `app/services/add_adult_registry_state.py` 已统一 adult pending / downloading 状态写入；`add_to_downloader.py` `582` 行只剩 proof-like wrapper，可先停手不回退。
- `search_media.py` 已降到 `288` 行，歧义澄清 / media-BT 排序 / batch preview 页面支持 helper 都已抽出；`import_to_library.py` 当前 `590` 行，经 focused gate + pyflakes 复核后继续保持 proof-like orchestration 冻结态。
- `cleanup_correlation_lookup.py` 已收回 task identity、correlation lookup、correlation logging 全部薄壳；`cleanup_downloaded_source.py` 已收回 inspect / path guard / query / event / flow / blocked / execution / follow-up / seed-guard / logging / 资产删除 全部薄壳；`adult_archive_service.py` 也不再依赖 cleanup 资产删除 helper。`cleanup_*_support.py` 当前为 `0` 个。
- `docs/TEST_ENV.md` 与 `tmp_tests/` 已按“彻底不用后删”退出活跃仓库真相；当前活跃 `docs/` 根目录 Markdown 为 `15` 个。

## Current health

- 代码热点线当前都已经回到 proof-like orchestration；cleanup 支持文件收口已经完成，这轮主风险不再是 cleanup 碎片文件，而是下一条结构债如果选得太大，会重新把范围做宽。
- 当前归档迁移和 cleanup 收口都已落地；下一条最小风险应切去新的重复代码或结构债，而不是回头再造 `cleanup_*_support.py`。

## Later candidate line

- 当前 cleanup 支持文件收口已经完成；如果后续要做用户可感知改进，统一蓝图再看 `docs/SEARCH_REPLY_PRESENTATION_PLAN.md`。
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
- `tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py`：`26 passed`
- 真实 smoke 保持通过态，本轮未改下载器 / 归档协议。

## Current biggest risk

- 当前 biggest risk 已不再是 cleanup 支持文件；下一轮如果继续减法，应该切去新的重复代码或结构债，而不是回头再造 `cleanup_*_support.py`。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

这轮 `cleanup_*_support.py` 收口已完成。若继续，默认不要回头重建 cleanup 薄壳；优先挑新的重复代码或结构债做一个最小闭环。
```
