# Current status (v470)

## Current mainline

- **质量硬化** 当前保持完成态，不回退。
- 当前默认分支主线已从“成人 BT 专线真实 smoke blocker 收口”切到 **成人 BT 专线第二条真实 smoke 收口**；direct magnet 入口继续保留“观影 PT 链 / BT 成人链”问询，不自动假定成人链。
- 成人 BT 当前新真相已落地：
  - `adult_content_registry` 已记录 `pending / downloading / archived_present / archived_deleted`
  - BT 预览 / 批量预览 / 待确认文本已能提示历史状态
  - 成人 BT 下载完成后可进入归档，统一保留窗口到期后可清理下载器任务与源资源
  - direct magnet 运行时选择 `BT 成人链` 时，已能直接创建成人磁力下载待确认并尽量识别番号 / 分类
  - qB 导入源解析已改成优先使用真实 `content_path`，不再盲信漂移的 `save_path`
  - qB 成人归档真实 smoke 已通过：归档成功、保留期清理成功、`adult_content_registry` 最终为 `archived_deleted`
- 三座大山保持完成态：`app/services/search_media.py` `568` 行，`add_to_downloader.py` `574` 行，`import_to_library.py` `585` 行。
- BT 来源适配当前保持：
  - 成人站点优先：`tokyotosho` / `sukebei(offkab)` / `javbus`
  - `Prowlarr` 成人 PT 作为补充来源
  - `javlibrary` helper 仍待补成只读识别补全

## Current health

- 当前这轮变更只触碰 qB 导入源解析、qB 成人归档真实 smoke 与文档真相，没有改 movie-first PT / import / metadata 主链协议。
- 当前最大风险不是 qB 这条链能不能成立，而是：
  - `19092` BT Transmission 侧还没有成人归档通过态证据
  - 当前 BT Transmission 真实 smoke 已能建任务，但任务长期停在 `status=4 / percentDone=0.0`

## Latest verification

- `make quality`：当前轮已按 blocker 文档真相重跑通过
- `make verify-mainline`：上一轮已通过；本轮未改 shared runtime 主链协议
- `make test`：`1891 passed, 0 skipped`
- `.venv/bin/python -m pyflakes`：
  - `app/clients/qbittorrent.py`、`tests/test_qbittorrent_client.py`、`tmp_tests/verify_adult_archive_qb_real_smoke.py` 全部通过
- focused pytest：
  - `tests/test_qbittorrent_client.py`：`7 passed`
- 运行时 focused：
  - `.venv/bin/python tmp_tests/verify_adult_archive_qb_real_smoke.py`：当前通过，证据文件 `/tmp/luminarr_adult_archive_qb_real_smoke/evidence.json`
  - `.venv/bin/python tmp_tests/verify_bt_transmission_rpc_probe.py`：当前产出 `/tmp/luminarr_bt_transmission_rpc_probe.json`，连续 `5/5` 次 `All connection attempts failed`
  - `bash -lc 'cd /home/alex/projects/luminarr && .venv/bin/python tmp_tests/verify_adult_archive_bt_real_smoke.py'`：当前产出 `/tmp/luminarr_adult_archive_bt_real_smoke/evidence.json`
  - qB 当前通过态证据包含：
    - `adult_archive.succeeded`
    - `adult_archive.retention_cleanup_succeeded`
    - `source_path_removed=true`
    - `qb_removed=true`
  - BT Transmission 当前 blocker 证据包含：
    - 任务已创建：`task_id=2`
    - `status_code=4`
    - `percent_done=0.0`
    - `rate_download=0`
    - `downloadDir=/data/downloads/tr-bt`

## Current biggest risk

- 当前最大不确定性已经从“qB real smoke 能不能通过”转成“BT Transmission 当前停在 `downloadDir=/data/downloads/tr-bt` + `status=4/0.0%`，这是不是 download_dir 宿主机/容器路径边界没对齐”。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

保持当前成人 BT 主线，先复验 `19092` BT Transmission 当轮可达性，再决定是补 BT Transmission 侧成人归档真实 smoke，还是先把 `19092` 波动收成 probe 证据。
```
