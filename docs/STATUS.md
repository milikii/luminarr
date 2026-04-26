# Current status (v482)

## Current mainline

- **质量硬化** 当前保持完成态，不回退。
- 当前默认分支主线切到 **`search_media.py` media-BT 排序 / batch preview helper 收口**；详细蓝图统一看 `docs/SEARCH_MEDIA_SLIMMING_LOG.md`。
- `Makefile` 公开验证入口与操作者入口文档已收口：`verify-mainline` 现在是 4 个分组 target 汇总入口，cleanup 公开入口收敛到 `test-cleanup-smoke` / `test-cleanup` / `test-cleanup-docs-gate` / `test-cleanup-window`，`docs/OPERATOR_RUNBOOK.md` / `docs/GETTING_STARTED.md` 已去掉过时残留。
- 成人 BT / qB / Transmission 当前真相继续保持：exact-id read-only helper 只补展示字段，helper-only 字段不进 truth，归档 / 保留期清理继续可用，真实归档 smoke 通过。
- `qB` 导入源解析继续优先真实 `content_path`；`DOWNLOADER_INSTANCES` 的 `dispatch_download_dir` 与宿主机导入路径保持分离；路由层继续优先任务真相里的 host `download_dir`。
- `app/services/add_adult_registry_state.py` 已统一 adult pending / downloading 状态写入；`add_to_downloader.py` `582` 行只剩 proof-like wrapper，可先停手不回退。
- `search_media.py` 已降到 `313` 行，歧义澄清 helper 和 media-BT 排序 helper 已抽出；当前热点大文件仍需留意：`app/services/search_media.py` `313` 行，`add_to_downloader.py` `582` 行，`import_to_library.py` `590` 行；`app/services/bt_read_only_display.py` `180` 行、`app/services/bt_read_only_helper_selection.py` `104` 行继续维持既有收口。

## Current health

- 这轮已经把 adult registry 的 pending / dispatch 两段统一到 `app/services/add_adult_registry_state.py`；downloader confirm 主线可以先停在 proof-like wrapper。
- 下一条风险集中到 `search_media.py`：batch preview 页面支持仍堆在同一热点文件里。
- 如果后续继续把 confirm / pending 小修直接落在壳文件里，主链维护成本会回升。

## Later candidate line

- 当前唯一执行主线仍然保持收口节奏；若后续显式切到消息展示体验层，统一蓝图看 `docs/SEARCH_REPLY_PRESENTATION_PLAN.md`。
- 这条后续候选主线固定为 `Telegram-first`：先做 Telegram richer reply，Feishu / personal WeChat / WeCom 首阶段先保留共享文本降级，不改 shared runtime / approval / dispatch 真相。
- 成人 BT 图片目标当前记为“尽量全量带图”，但实施分阶段；拿不到稳定图源时明确降级为纯文本。

## Latest verification

- `make quality`：`32 passed, 0 skipped`
- `make verify-mainline`：当前轮已通过
- focused pytest：
  - `tests/test_add_execution_follow_up.py tests/test_add_to_downloader.py tests/test_private_chat_confirm_runtime.py`：`125 passed`
  - `tests/test_search_ambiguity_helper.py tests/test_search_media.py -k "ambiguous or clarification"`：`15 passed, 173 deselected`
  - `tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py`：`32 passed`
- 真实 smoke 保持通过态，本轮未改下载器 / 归档协议。

## Current biggest risk

- `search_media.py` 现为 `313` 行；若下一轮继续把 batch preview 小修直接堆回主文件，`app/services/search_media.py` 的候选持久化、只读展示和 query fallback 维护成本会重新回升。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

这轮主线切到 search_media.py helper 收口：只收 media-BT 排序 helper、batch preview 页面支持 helper 这两组稳定职责；优先做一个可验证的小闭环，不改 candidate / clarification / BT helper truth 或 shared runtime 边界。
```
