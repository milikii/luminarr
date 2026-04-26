# Current status (v487)

## Current mainline

- **质量硬化** 当前保持完成态，不回退。
- 当前默认分支主线切到 **`cleanup_*_support.py` 代码碎片收口 / 质量硬化**：上一轮已经把 `docs/` 主目录历史施工文档移到 `archive/docs/`，现在开始收 cleanup 链里只服务单点的微型 helper。
- `Makefile` 公开验证入口与操作者入口文档已收口：`verify-mainline` 现在是 4 个分组 target 汇总入口，cleanup 公开入口收敛到 `test-cleanup-smoke` / `test-cleanup` / `test-cleanup-docs-gate` / `test-cleanup-window`，`docs/OPERATOR_RUNBOOK.md` / `docs/GETTING_STARTED.md` 已去掉过时残留。
- 成人 BT / qB / Transmission 当前真相继续保持：exact-id read-only helper 只补展示字段，helper-only 字段不进 truth，归档 / 保留期清理继续可用，真实归档 smoke 通过。
- `qB` 导入源解析继续优先真实 `content_path`；`DOWNLOADER_INSTANCES` 的 `dispatch_download_dir` 与宿主机导入路径保持分离；路由层继续优先任务真相里的 host `download_dir`。
- `app/services/add_adult_registry_state.py` 已统一 adult pending / downloading 状态写入；`add_to_downloader.py` `582` 行只剩 proof-like wrapper，可先停手不回退。
- `search_media.py` 已降到 `288` 行，歧义澄清 / media-BT 排序 / batch preview 页面支持 helper 都已抽出；`import_to_library.py` 当前 `590` 行，经 focused gate + pyflakes 复核后继续保持 proof-like orchestration 冻结态。
- `cleanup_correlation_lookup.py` 已收回 `cleanup_correlation_event_support.py` / `cleanup_correlation_flow_support.py` / `cleanup_correlation_result_support.py` 三个微文件；`cleanup_downloaded_source.py` 已收回 `cleanup_inspect_flow_support.py` / `cleanup_path_guard_support.py` / `cleanup_query_support.py` / `cleanup_event_support.py` 四个薄壳；`cleanup_flow_support.py` 已收回 `cleanup_blocked_support.py` / `cleanup_execution_support.py` / `cleanup_follow_up_support.py` / `cleanup_inspect_render_support.py`；`cleanup_logging_support.py` 已收回 `cleanup_correlation_logging_support.py`；`cleanup_*_support.py` 现剩 6 个。
- `docs/TEST_ENV.md` 与 `tmp_tests/` 已按“彻底不用后删”退出活跃仓库真相；当前活跃 `docs/` 根目录 Markdown 为 `15` 个。

## Current health

- 代码热点线当前都已经回到 proof-like orchestration；这轮主风险转到了 cleanup 链的小文件碎片化，如果不继续收口，`cleanup_*_support.py` 很快又会堆回去。
- 当前归档迁移已经落地，cleanup 入口已经收回一批薄壳，但 `cleanup_*_support.py` 仍需继续收口，避免把“单点薄壳”继续留在主目录。

## Later candidate line

- 当前唯一执行主线已经切到 `cleanup_*_support.py` 碎片收口；如果后续要做用户可感知改进，统一蓝图再看 `docs/SEARCH_REPLY_PRESENTATION_PLAN.md`。
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
- `tests/test_cleanup_downloaded_source.py tests/test_cleanup_docs_consistency.py`：`56 passed`
- `tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py`：`26 passed`
- 真实 smoke 保持通过态，本轮未改下载器 / 归档协议。

## Current biggest risk

- `cleanup_*_support.py` 还剩 6 个碎片文件；如果下一轮不继续收口这些真正的薄壳，cleanup 链会很快又回到碎片化。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

这轮主线切到 `cleanup_*_support.py` 代码碎片收口：只收 cleanup 链里能合并的薄壳，不回头拆 `search_media.py` / `import_to_library.py` / `add_to_downloader.py`。
```
