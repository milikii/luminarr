# Current status (v501)

## Current mainline
- **质量硬化** 继续保持完成态；**文档入口收口 / 当前真相对齐** 已完成并推送；当前切回 **质量债硬化 / 小 support 文件收口 + 异常边界收窄**。
- 本轮已收掉 5 个小单消费者 support 文件：`bt_subscription_dispatch_support.py`、`bt_subscription_last_seen_support.py`、`bt_subscription_scan_support.py`、`bt_subscription_scheduler_support.py`、`search_media_batch_preview_support.py`。
- 本轮已收窄 3 处异常边界：import transfer 残留清理只捕获文件 I/O 异常，TMDB fallback 只捕获 HTTP/JSON 响应异常，WeCom base64 解码只捕获 `binascii.Error`。
- 成人 BT 不是空白：当前已有 PT/BT 分流、BT 成人链问询、成人归档目录配置、`adult_content_registry`、归档保留期清理、只读补全和展示基础；但成人 BT 继续扩功能不是本轮主线。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支最近业务回归保持绿灯；本轮 focused tests 已覆盖 import transfer、search media、BT subscription、WeCom 和 docs gate。
- 下一轮如果继续质量债，优先挑剩余 broad `except Exception`、日志打印边界或 `main()` DI；不要为了凑数字强拆剩余大 support 文件。

## Latest verification
- `tests/test_cleanup_docs_consistency.py`：`8 passed`
- `tests/test_import_to_library.py -k "copy_fallback or hardlink or target_exists or import_transfer"`：`12 passed, 137 deselected`
- `tests/test_persistence_sqlite.py -k "copy_fallback_pending_survives_restart_and_second_confirm_copies or unexpected_hardlink"`：`1 passed, 110 deselected`
- `tests/test_search_media.py -k "tmdb_failed or tmdb_failure"`：`2 passed, 183 deselected`
- `tests/test_manage_bt_subscription.py tests/test_bt_subscription_*_support.py`：`48 passed`
- `tests/test_search_media_batch_preview_support.py tests/test_search_media.py -k "bt_batch_preview or batch_preview or page_url"`：`70 passed, 118 deselected`
- `tests/test_wecom_adapter.py`：`33 passed, 4 warnings`
- `tests/test_config.py`：`39 passed, 0 skipped`
- `tests/test_config.py tests/test_downloader_route_lookup.py tests/test_main.py`：`71 passed, 4 warnings`
- `make quality`：通过（`27 passed`）
- `make verify-mainline`：通过

## Current biggest risk
- 剩余 broad `except Exception` 里有一部分是外部服务降级边界，不能机械替换；下一步必须逐个按真实异常类型和测试覆盖判断。
- 当前成人 BT 后续仍可作为候选主线，但默认不切功能；继续质量债时以“最小、可验证、不扩协议”为准。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线是质量债硬化。优先从剩余 broad except、日志打印边界或 `main()` DI 里挑一个最小闭环；不要重建已收掉的小 support 文件，不要切成人 BT 新功能，不改协议或 SQLite 真相边界。
```
