# Current status (v469)

## Current mainline

- **质量硬化** 当前保持完成态，不回退。
- 当前默认分支主线已从“成人 BT 专线质量复验”切到 **成人 BT 专线真实 smoke blocker 收口**；direct magnet 入口继续保留“观影 PT 链 / BT 成人链”问询，不自动假定成人链。
- 成人 BT 当前新真相已落地：
  - `adult_content_registry` 已记录 `pending / downloading / archived_present / archived_deleted`
  - BT 预览 / 批量预览 / 待确认文本已能提示历史状态
  - 成人 BT 下载完成后可进入归档，统一保留窗口到期后可清理下载器任务与源资源
  - direct magnet 运行时选择 `BT 成人链` 时，已能直接创建成人磁力下载待确认并尽量识别番号 / 分类
  - qB 导入源解析已改成优先使用真实 `content_path`，不再盲信漂移的 `save_path`
- 三座大山保持完成态：`app/services/search_media.py` `568` 行，`add_to_downloader.py` `574` 行，`import_to_library.py` `585` 行。
- BT 来源适配当前保持：
  - 成人站点优先：`tokyotosho` / `sukebei(offkab)` / `javbus`
  - `Prowlarr` 成人 PT 作为补充来源
  - `javlibrary` helper 仍待补成只读识别补全

## Current health

- 当前这轮变更只触碰 qB 导入源解析、adult archive real smoke 探针与文档真相，没有改 movie-first PT / import / metadata 主链协议。
- 当前最大风险不是主链是否成立，而是：
  - qB 测试栈目录 `/data/downloads/qb`、`/data/downloads/incomplete-qb` 当前权限与 compose 的 `PUID=1000/PGID=1000` 不一致，real smoke 卡在真实文件落盘
  - `19092` BT Transmission 当前仍不可达，成人归档 sidecar 还没有 BT Transmission 侧证据

## Latest verification

- `make quality`：当前轮已按 blocker 文档真相重跑通过
- `make verify-mainline`：上一轮已通过；本轮未改 shared runtime 主链协议
- `make test`：`1891 passed, 0 skipped`
- `.venv/bin/python -m pyflakes`：
  - `app/clients/qbittorrent.py`、`tests/test_qbittorrent_client.py`、`tmp_tests/verify_adult_archive_qb_real_smoke.py` 全部通过
- focused pytest：
  - `tests/test_qbittorrent_client.py`：`7 passed`
- 运行时 focused：
  - `.venv/bin/python tmp_tests/verify_adult_archive_qb_real_smoke.py`：当前已稳定产出 blocker 证据 `/tmp/luminarr_adult_archive_qb_real_smoke/evidence.json`
  - 当前证据显示 qB 任务 `content_path=/data/downloads/incomplete-qb/SSIS-123-smoke.mp4`、`save_path=/data/downloads/qb/luminarr_adult_archive_smoke`，同时 qB 日志命中 `file_open ... Permission denied` 与 `storage move failed. mkdir(): Permission denied`

## Current biggest risk

- 当前最大不确定性已经从“repo 侧 qB 路径解析是否正确”转成“先修 qB 下载目录权限，还是先恢复 `19092` BT Transmission 可达性来拿第二条真实 smoke 证据”。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

先收口成人 BT qB real smoke blocker，优先核对 `/data/downloads/qb` 与 `/data/downloads/incomplete-qb` 权限，再重跑 `tmp_tests/verify_adult_archive_qb_real_smoke.py`。
```
