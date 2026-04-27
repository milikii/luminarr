# Current status (v499)

## Current mainline
- **质量硬化** 当前保持完成态，不回退。
- `config.py` 重复解析逻辑已收口：`RAW_BT_DESTINATIONS` / `ADULT_ARCHIVE_DESTINATIONS` / `DOWNLOADER_INSTANCES` 共用解析 helper，base URL 也统一走 shared normalization helper，且读 base URL 的 env 路径也抽成了 `_read_base_url`，`DOWNLOADER_INSTANCES` 里的 base URL 现在也走同一个 helper，`FEISHU_INBOUND_MODE` / `MEDIA_SERVER_PROVIDER` / `DOWNLOADER_INSTANCES.downloader_type` / `*_optional_int*` / `SUBTITLE_TRANSLATION_TIMEOUT_SECONDS` 也共用 shared validator helper。
- `app/downloader_route_lookup.py` 当前 `267` 行；task route / dispatch 日志已直接落到共享打印器，instance strip/lookup 与 host `download_dir` fallback 已收口，`_log_*` 已归零，`_resolve_route_host_download_dir` 这个单消费者薄壳已删，`_resolve_downloader_client_candidate` 已收回到两个实际调用点，`_resolve_downloader_instance_and_client` 现在承接两条真实调用点，`_resolve_downloader_task_route` 已从两字段 dataclass 收成 tuple，`_resolve_downloader_client_for_dispatch` 和 `resolve_downloader_dispatch_download_dir` 现已挪到 `app/main.py`，`import` 路由里的 host `download_dir` 回填现在直接用 `route.download_dir` / `instance.download_dir` 合并结果，不再保留空的 `instance is None` 兜底分支。
- `app/main.py` 当前 `482` 行；下载器投递分流 helper 现在由 main 编排层持有，`_resolve_downloader_client_for_dispatch` 与 `resolve_downloader_dispatch_download_dir` 都已迁入这里，BT source provider 组装和 fanart / download_image 的顶层壳也已收进 `main()`。
- `app/services/search_media.py` 当前 `274` 行；BT batch preview 缓存转手壳已并回调用点，`_to_candidate_dict` / `_attach_media_identity_to_candidate` 也已收口到 inline 变换。
- `app/services/metadata_scraper.py` 当前 `384` 行；metadata / NFO sidecar 路径、图片 artifact 路径、字符串归一化、text artifact 写入和 NFO 拼装小壳都已并回入口。
- `cleanup_*_support.py` 当前为 `0` 个；cleanup 收口、重复 trace logger、`_COMPAT_REEXPORTS`、无消费者 `__all__` 都已保持完成态。
- `app/main.py` 残余 downloader client 死壳已删，`tests/test_main.py` 现在直接 import `app.downloader_route_lookup` 真实边界。

## Current health
- 代码热点线已回到 proof-like orchestration；`downloader_route_lookup.py` 现在已把 resolved `instance` 直接带回 import 路由，且 `_resolve_downloader_instance` / `_resolve_downloader_client_candidate` 这两层薄壳都已删，dispatch 选择逻辑已迁到 `app/main.py`，当前最小风险转为是否还值得继续压薄 `app/main.py` 里的这两个 dispatch helper，或干脆停在当前壳收口态。
- 当前归档迁移、cleanup 收口、trace logger 收口、`config.py` 收口、`app/main.py` 死壳清理和 route helper 错误边界修正都已落地；cleanup hardlink 语义保持原状，新增的 adult archive 2 参兼容回归也已补上。

## Latest verification
- `tests/test_config.py`：`39 passed, 0 skipped`
- `tests/test_config.py tests/test_downloader_route_lookup.py tests/test_main.py`：`71 passed, 4 warnings`
- `tests/test_downloader_route_lookup.py tests/test_main.py`：`34 passed, 4 warnings`
- `.venv/bin/python -m pytest tests/test_main.py tests/test_downloader_route_lookup.py`：`34 passed, 4 warnings`
- `tests/test_cleanup_downloaded_source.py tests/test_cleanup_cross_channel_smoke.py`：`425 passed, 4 warnings`
- `make quality`：通过
- `make verify-mainline`：通过

## Current biggest risk
- 当前 biggest risk 已不再是 cleanup 支持文件、trace logger 重复壳、`_COMPAT_REEXPORTS` 或 `config.py`；下一轮如果继续减法，应只沿 `app/main.py`、`app/services/search_media.py` 或 `app/services/metadata_scraper.py` 里还能再压薄的单消费者 helper 推进，而不是把范围扩成整份路由系统重写。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

这轮 `downloader_route_lookup.py` 的 task/downloader 日志上下文、payload 解析/读取、lookup 抛错、status/remove 路由序幕和 import download_dir 回填壳已继续收口。若继续，默认不要回头重建 cleanup 薄壳、workflow trace 壳或兼容 tuple；优先挑 `downloader_route_lookup.py` 剩余单消费者 helper 或 route 死壳做一个更小闭环。
```
