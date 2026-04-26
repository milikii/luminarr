# Current status (v472)

## Current mainline

- **质量硬化** 当前保持完成态，不回退。
- 当前默认分支主线已从 **`javlibrary` helper 只读识别补全** 切到 **成人标题归一化回归保护**；direct magnet 入口继续保留“观影 PT 链 / BT 成人链”问询，不自动假定成人链。
- 成人 BT 当前新真相已落地：
  - `adult_content_registry` 已记录 `pending / downloading / archived_present / archived_deleted`
  - BT 预览 / 批量预览 / 待确认文本已能提示历史状态
  - `bt搜` / `bt批量` 当前已接入 `javlibrary` exact-id only 只读补全，可显示 `display_id / category / title`，并复用历史状态查询
  - `bt批量` 候选缓存当前只保留原始候选；`javlibrary` helper-only 字段不会进入 `candidate_mapping`、待确认下载或 downloader dispatch 真相
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
  - `javlibrary` 当前定位已经收口为 **BT-only read-only exact-id helper**，不放宽成自动 dispatch 来源

## Current health

- 当前这轮变更只触碰 `javlibrary` helper、BT 只读展示/缓存边界和文档真相，没有改 downloader dispatch、approval、import 或 metadata 主链协议。
- 当前成人 BT 主线的两条真实 smoke 继续保持通过态；当前更需要留意的是：
  - `javlibrary` 当前只补 exact-id only 只读场景；非 exact-id 的噪声标题仍主要依赖站点标题和既有规则
  - 后续如果继续补成人标题归一化，只能做更窄的 focused tests / normalization guard，不能反向把 helper 结果写进审批真相

## Latest verification

- `make quality`：当前轮已通过
- `make verify-mainline`：当前轮已通过
- focused pytest：
  - `tests/test_search_media.py tests/test_private_chat_bt_read_only_runtime.py tests/test_private_chat_bt_batch_confirm_runtime.py tests/test_javlibrary_helper.py tests/test_adult_content.py`：当前通过
- 真实 smoke 保持通过态，本轮未改下载器 / 归档协议：
  - `.venv/bin/python tmp_tests/verify_adult_archive_qb_real_smoke.py`：上一轮通过，证据文件 `/tmp/luminarr_adult_archive_qb_real_smoke/evidence.json`
  - `bash -lc 'cd /home/alex/projects/luminarr && .venv/bin/python tmp_tests/verify_adult_archive_bt_real_smoke.py'`：上一轮通过，证据文件 `/tmp/luminarr_adult_archive_bt_real_smoke/evidence.json`
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

- 当前最大不确定性已经从“`javlibrary` helper 能不能收口”转成“后续成人标题归一化如果继续推进，如何继续把它限定在更窄的 read-only / focused-regression 边界内，而不反向污染 dispatch 主链”。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

保持质量硬化，不新增用户可感知功能。`javlibrary` helper 已收口为 BT-only read-only exact-id helper；下一步沿着“成人标题归一化回归保护”推进，只补更窄的 focused tests / normalization guard，不放宽成自动 dispatch 来源。
```
