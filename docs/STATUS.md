# Current status (v482)

## Current mainline

- **质量硬化** 当前保持完成态，不回退。
- 当前默认分支主线仍是 **`add_to_downloader.py` confirm wrapper 收口 / 质量硬化**；详细蓝图统一看 `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`。
- `Makefile` 公开验证入口与操作者入口文档已收口：`verify-mainline` 现在是 4 个分组 target 汇总入口，cleanup 公开入口收敛到 `test-cleanup-smoke` / `test-cleanup` / `test-cleanup-docs-gate` / `test-cleanup-window`，`docs/OPERATOR_RUNBOOK.md` / `docs/GETTING_STARTED.md` 已去掉过时残留。
- 成人 BT / qB / Transmission 当前真相继续保持：exact-id read-only helper 只补展示字段，helper-only 字段不进 truth，归档 / 保留期清理继续可用，真实归档 smoke 通过。
- `qB` 导入源解析继续优先真实 `content_path`；`DOWNLOADER_INSTANCES` 的 `dispatch_download_dir` 与宿主机导入路径保持分离；路由层继续优先任务真相里的 host `download_dir`。
- 当前热点大文件仍需留意：`app/services/search_media.py` `628` 行，`add_to_downloader.py` `582` 行，`import_to_library.py` `590` 行；`app/services/bt_read_only_display.py` `180` 行、`app/services/bt_read_only_helper_selection.py` `104` 行继续维持既有收口。

## Current health

- 这轮已经把 `adult pending` 写入壳从 `add_to_downloader.py` 抽到 `app/services/add_adult_pending_state.py`，下一条风险集中到成人 registry 状态写入仍分散在 pending / dispatch 两段。
- 如果后续继续把 confirm / pending 小修直接落在壳文件里，主链维护成本会回升。

## Later candidate line

- 当前唯一执行主线仍然保持收口节奏；若后续显式切到消息展示体验层，统一蓝图看 `docs/SEARCH_REPLY_PRESENTATION_PLAN.md`。
- 这条后续候选主线固定为 `Telegram-first`：先做 Telegram richer reply，Feishu / personal WeChat / WeCom 首阶段先保留共享文本降级，不改 shared runtime / approval / dispatch 真相。
- 成人 BT 图片目标当前记为“尽量全量带图”，但实施分阶段；拿不到稳定图源时明确降级为纯文本。

## Latest verification

- `make quality`：`32 passed, 0 skipped`
- `make verify-mainline`：当前轮已通过
- focused pytest：
  - `tests/test_makefile.py tests/test_cleanup_docs_consistency.py`：`25 passed`
  - `make test-docs`：`20 passed`
- 真实 smoke 保持通过态，本轮未改下载器 / 归档协议。

## Current biggest risk

- `add_to_downloader.py` 现为 `582` 行；若下一轮不把成人 registry 状态写入继续收回统一 helper，而是回到 approval / lease / confirm 顺序本体，维护风险会重新上升。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

这轮主线继续 add_to_downloader.py confirm wrapper 收口：优先把成人 registry 状态写入继续从 pending / dispatch 两段统一收口，再评估是否还剩稳定 wrapper 可动；不改 approval / lease / confirm / downloader dispatch / import 真相边界。
```
