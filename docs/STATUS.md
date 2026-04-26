# Current status (v471)

## Current mainline

- **质量硬化** 当前保持完成态，不回退。
- 当前默认分支主线已从 **成人 BT 专线第二条真实 smoke 收口** 切到 **`javlibrary` helper 只读识别补全**；direct magnet 入口继续保留“观影 PT 链 / BT 成人链”问询，不自动假定成人链。
- 成人 BT 当前新真相已落地：
  - `adult_content_registry` 已记录 `pending / downloading / archived_present / archived_deleted`
  - BT 预览 / 批量预览 / 待确认文本已能提示历史状态
  - 成人 BT 下载完成后可进入归档，统一保留窗口到期后可清理下载器任务与源资源
  - direct magnet 运行时选择 `BT 成人链` 时，已能直接创建成人磁力下载待确认并尽量识别番号 / 分类
  - qB 导入源解析已改成优先使用真实 `content_path`，不再盲信漂移的 `save_path`
  - `DOWNLOADER_INSTANCES` 当前可选第 5 段 `dispatch_download_dir`；容器化下载器可把“下载器 API 投递路径”和“宿主机导入路径”分开表达
  - 路由层当前会在导入查询时优先恢复任务真相里的 host `download_dir`，不再把 Transmission RPC 的容器路径直接喂给归档/导入
  - qB 成人归档真实 smoke 已通过：归档成功、保留期清理成功、`adult_content_registry` 最终为 `archived_deleted`
  - BT Transmission 成人归档真实 smoke 已通过：归档成功、保留期清理成功、`adult_content_registry` 最终为 `archived_deleted`
- 三座大山保持完成态：`app/services/search_media.py` `568` 行，`add_to_downloader.py` `574` 行，`import_to_library.py` `585` 行。
- BT 来源适配当前保持：
  - 成人站点优先：`tokyotosho` / `sukebei(offkab)` / `javbus`
  - `Prowlarr` 成人 PT 作为补充来源
  - `javlibrary` helper 仍待补成只读识别补全

## Current health

- 当前这轮变更只触碰 downloader 路由、BT Transmission 真实 smoke 和文档真相，没有改 movie-first PT / import / metadata 主链协议。
- 当前成人 BT 主线的两条真实 smoke 都已有通过态证据；当前更需要留意的是：
  - 本地容器化 Transmission 若仍只配置 host `download_dir`、未补 `dispatch_download_dir`，就可能继续把宿主机路径直接发给下载器 API
  - `javlibrary` helper 仍缺只读识别补全，成人标题识别目前还不能把该来源当成稳定只读补充

## Latest verification

- `make quality`：当前轮已通过
- `make verify-mainline`：上一轮已通过；本轮未改 shared runtime 主链协议
- `.venv/bin/python -m pyflakes`：
  - `tmp_tests/verify_adult_archive_bt_real_smoke.py` 通过
- focused pytest：
  - `tests/test_config.py tests/test_downloader_route_lookup.py`：`36 passed, 0 skipped`
- 运行时 focused：
  - `.venv/bin/python tmp_tests/verify_adult_archive_qb_real_smoke.py`：当前通过，证据文件 `/tmp/luminarr_adult_archive_qb_real_smoke/evidence.json`
  - `bash -lc 'timeout 5 curl -si http://127.0.0.1:19092/transmission/rpc'`：当前返回 `409 + X-Transmission-Session-Id`
  - `bash -lc 'cd /home/alex/projects/luminarr && .venv/bin/python tmp_tests/verify_adult_archive_bt_real_smoke.py'`：当前通过，证据文件 `/tmp/luminarr_adult_archive_bt_real_smoke/evidence.json`
  - qB 当前通过态证据包含：
    - `adult_archive.succeeded`
    - `adult_archive.retention_cleanup_succeeded`
    - `source_path_removed=true`
    - `qb_removed=true`
  - BT Transmission 当前通过态证据包含：
    - `session_snapshot.download_dir=/downloads/complete`
    - `archive_reply=成人资源归档成功`
    - `cleanup_reply=成人资源保留期清理完成`
    - `registry_statuses.after_archive=archived_present`
    - `registry_statuses.after_cleanup=archived_deleted`

## Current biggest risk

- 当前最大不确定性已经从“BT Transmission 第二条真实 smoke 能不能收口”转成“后续成人 ID 补全是否要继续把 `javlibrary` 限定在 BT-only read-only helper 边界内，而不反向污染 dispatch 主链”。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

保持质量硬化，不新增用户可感知功能。沿着 `javlibrary` helper 只读识别补全这条新主线推进，只做 BT-only read-only 识别补充，不放宽成自动 dispatch 来源。
```
