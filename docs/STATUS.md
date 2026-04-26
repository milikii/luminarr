# Current status (v469)

## Current mainline

- **质量硬化** 当前保持完成态，不回退。
- 当前默认分支主线已从“成人 BT 专线基础收口”切到 **成人 BT 专线质量复验**；direct magnet 入口继续保留“观影 PT 链 / BT 成人链”问询，不自动假定成人链。
- 成人 BT 当前新真相已落地：
  - `adult_content_registry` 已记录 `pending / downloading / archived_present / archived_deleted`
  - BT 预览 / 批量预览 / 待确认文本已能提示历史状态
  - 成人 BT 下载完成后可进入归档，统一保留窗口到期后可清理下载器任务与源资源
  - direct magnet 运行时选择 `BT 成人链` 时，已能直接创建成人磁力下载待确认并尽量识别番号 / 分类
- 三座大山保持完成态：`app/services/search_media.py` `568` 行，`add_to_downloader.py` `574` 行，`import_to_library.py` `585` 行。
- BT 来源适配当前保持：
  - 成人站点优先：`tokyotosho` / `sukebei(offkab)` / `javbus`
  - `Prowlarr` 成人 PT 作为补充来源
  - `javlibrary` helper 仍待补成只读识别补全

## Current health

- 当前这轮变更只触碰 direct magnet follow-up 与成人下载完成 sidecar 的回归边界，没有改 movie-first PT / import / metadata 主链协议。
- 当前最大风险不是主链是否成立，而是：
  - 成人归档 sidecar 与现有 auto-import sidecar 的共存还缺一次更大的 gate / real smoke
  - `javlibrary` 仍只停留在后续只读 helper 口径，尚未补成实际识别补全

## Latest verification

- `make quality`：当前轮已按最终文档真相重跑通过
- `make verify-mainline`：当前轮已按 direct magnet 新边界重跑通过
- `make test`：`1888 passed, 2 skipped`
- `.venv/bin/python -m pyflakes`：
  - direct magnet follow-up / 成人归档回归相关改动文件全部通过
- focused pytest：
  - `tests/test_query_text_runtime.py tests/test_private_chat_bt_processing_runtime.py`：`11 passed`
  - `tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k "magnet_routes_to_bt_direct_split or bt_processing_path or handle_bt_direct_intent_query"`：`26 passed`
  - `tests/test_get_download_status.py -k "post_download_auto_import"`：`16 passed`
- 运行时 focused：
  - `make verify-mainline` 当前轮已完整重跑 direct magnet / shared runtime / Telegram 相关子集，未见业务红灯
  - `adult_content_registry` 命中后的归档 sidecar / `archived_deleted` skip 回归已补 focused 断言

## Current biggest risk

- 当前最大不确定性已经从“direct magnet 文档与代码是否一致”转成“下一步是先做成人归档 sidecar 的 real smoke，还是先补 `javlibrary` 只读 helper”。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

保持当前成人 BT 主线，并继续让 direct magnet 先问链路，不自动改成成人 BT 直投。
```
