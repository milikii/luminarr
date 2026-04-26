# Current status (v484)

## Current mainline

- **质量硬化** 当前保持完成态，不回退。
- 当前默认分支主线切到 **历史 docs 归档减法 / 质量硬化**：把已完成主线的 `*_PLAN.md` / `*_SLIMMING_LOG.md` / 历史风险日志从 `docs/` 主目录移到 `archive/docs/`，只保留当前入口、当前真相、长期边界和仍活跃的候选蓝图。
- `Makefile` 公开验证入口与操作者入口文档已收口：`verify-mainline` 现在是 4 个分组 target 汇总入口，cleanup 公开入口收敛到 `test-cleanup-smoke` / `test-cleanup` / `test-cleanup-docs-gate` / `test-cleanup-window`，`docs/OPERATOR_RUNBOOK.md` / `docs/GETTING_STARTED.md` 已去掉过时残留。
- 成人 BT / qB / Transmission 当前真相继续保持：exact-id read-only helper 只补展示字段，helper-only 字段不进 truth，归档 / 保留期清理继续可用，真实归档 smoke 通过。
- `qB` 导入源解析继续优先真实 `content_path`；`DOWNLOADER_INSTANCES` 的 `dispatch_download_dir` 与宿主机导入路径保持分离；路由层继续优先任务真相里的 host `download_dir`。
- `app/services/add_adult_registry_state.py` 已统一 adult pending / downloading 状态写入；`add_to_downloader.py` `582` 行只剩 proof-like wrapper，可先停手不回退。
- `search_media.py` 已降到 `288` 行，歧义澄清 / media-BT 排序 / batch preview 页面支持 helper 都已抽出；`import_to_library.py` 当前 `590` 行，经 focused gate + pyflakes 复核后继续保持 proof-like orchestration 冻结态。
- 当前文档减法已把 `docs/` 顶层 Markdown 从 `47` 个收口到 `18` 个；29 个已完成 `*_PLAN.md` / `*_SLIMMING_LOG.md` / 历史风险日志已移到 `archive/docs/`，当前热点代码文件仍保持：`app/services/search_media.py` `288` 行、`add_to_downloader.py` `582` 行、`import_to_library.py` `590` 行；当前入口改为按需回查归档。

## Current health

- 代码热点线当前都已经回到 proof-like orchestration；这轮主风险不在业务代码，而在历史文档继续堆在主 `docs/` 目录时，会让操作者和 AI 入口继续漂移。
- 当前归档迁移已经落地，但 `README.md`、`docs/HUMAN_START_HERE.md`、`docs/OPERATOR_RUNBOOK.md`、少量历史计划口径仍需继续收口，避免继续把后续接手人带回已完成主线。

## Later candidate line

- 当前唯一执行主线仍然保持文档减法收口节奏；若这一轮归档减法完成后还要继续做用户可感知改进，统一蓝图看 `docs/SEARCH_REPLY_PRESENTATION_PLAN.md`。
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
  - `tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py`：`25 passed`
- 真实 smoke 保持通过态，本轮未改下载器 / 归档协议。

## Current biggest risk

- 若归档迁移只停在“文件挪走”而不继续收入口漂移，后续操作者仍会被 `README` / runbook / 历史计划带回已完成主线，cleanup 收益会被快速吃掉。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

这轮主线切到历史 docs 归档减法：只做 `docs/` 主目录减法、入口文档与 docs gate 收口，不改业务代码。优先保持当前活跃文档留在 `docs/`，已完成主线台账移到 `archive/docs/`。
```
