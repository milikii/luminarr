# Current status (v476)

## Current mainline

- **质量硬化** 当前保持完成态，不回退。
- 当前默认分支主线 **BT 只读候选相关性保护** 已收口完成；若继续施工，下一步优先看 **BT 只读 helper 介入时机 / 只读截断策略继续收窄**。direct magnet 入口继续保留“观影 PT 链 / BT 成人链”问询，不自动假定成人链。
- 成人 BT 当前新真相已落地：
  - `adult_content_registry` 已记录 `pending / downloading / archived_present / archived_deleted`
  - BT 预览 / 批量预览 / 待确认文本已能提示历史状态
  - `bt搜` / `bt批量` 当前已接入 `javlibrary` exact-id only 只读补全，可显示 `display_id / category / title`，并复用历史状态查询
  - `bt批量` 候选缓存当前只保留原始候选；`javlibrary` helper-only 字段不会进入 `candidate_mapping`、待确认下载或 downloader dispatch 真相
  - 成人标题识别当前会先归一化全角 / 变体分隔符；`FC2`、`censored`、`uncensored` exact-id 输入会落到同一条识别真相
  - `caribbeancom / carib`、`1pondo / 1pon`、`10musume / 10mu`、`pacopacomama / paco` 当前会收口到同一 `normalized_content_id`
  - `一本道 / カリビアンコム / 天然むすめ / パコパコママ / 東京熱` 这类常见本地化站点别名当前会先归一化到既有 exact-id 规则
  - 常见分辨率 / 编码 / 字幕 / 流出噪声词当前会在 exact-id 提取前先剥离，不再要求标题足够“干净”才命中番号
  - keyword-only 成人分类猜测当前不会再写进 BT 候选真相、待确认上下文或 JavLibrary helper 入口；这些路径只接受 exact-id
  - JavLibrary helper 当前只会给和当前 exact-id 仍有明显标题关联的只读候选补元数据，不再把 query 级补全误贴到无关噪声结果
  - 只读展示当前会压掉“仅空格/连接符差异”的重复 helper 标题行
  - 成人 BT 只读排序当前已补 source alias 优先级归一化：`offkab / sukebei.nyaa.si / javbus.com / tokyotosho.info` 这类真实来源别名会吃到既有站点优先级
  - 非 exact-id 只读查询当前会先按标题相关性重排，再按站点优先级 / 做种数收口，不再轻易让无关高种噪声标题排到相关候选前面
  - exact-id 只读查询当前会优先展示标题表面就带明确番号的候选，再回退到 generic title + 站点补完
  - 同一番号的多候选当前只显示一次历史提示，不再在整段只读预览里重复刷屏
  - `bt搜` / `bt批量` 当前会在 top-N / 默认预览切片前先前置和 exact-id helper 明显相关的原始候选，减少边界噪声把相关条目挤出只读展示
  - `bt批量` 显式 selection 与 chat 缓存当前复用同一 helper-aware 顺序，但 helper-only 字段仍不会进入 `candidate_mapping`、待确认下载或 downloader dispatch 真相
  - 成人 BT 下载完成后可进入归档，统一保留窗口到期后可清理下载器任务与源资源
  - direct magnet 运行时选择 `BT 成人链` 时，已能直接创建成人磁力下载待确认并尽量识别番号 / 分类
  - qB 导入源解析已改成优先使用真实 `content_path`，不再盲信漂移的 `save_path`
  - `DOWNLOADER_INSTANCES` 当前可选第 5 段 `dispatch_download_dir`；容器化下载器可把“下载器 API 投递路径”和“宿主机导入路径”分开表达
  - 路由层当前会在导入查询时优先恢复任务真相里的 host `download_dir`，不再把 Transmission RPC 的容器路径直接喂给归档/导入
  - qB 成人归档真实 smoke 已通过：归档成功、保留期清理成功、`adult_content_registry` 最终为 `archived_deleted`
  - BT Transmission 成人归档真实 smoke 已通过：归档成功、保留期清理成功、`adult_content_registry` 最终为 `archived_deleted`
- 当前热点大文件仍需留意：`app/services/search_media.py` `778` 行，`add_to_downloader.py` `606` 行，`import_to_library.py` `649` 行；本轮已把 BT 只读 helper relevance 选择抽到 `app/services/bt_read_only_helper_selection.py` `97` 行，未改对外协议。
- BT 来源适配当前保持：
  - 成人站点优先：`tokyotosho` / `sukebei(offkab)` / `javbus`
  - `Prowlarr` 成人 PT 作为补充来源
  - `javlibrary` 当前定位已经收口为 **BT-only read-only exact-id helper**，不放宽成自动 dispatch 来源

## Current health

- 当前这轮变更只触碰 BT 只读 helper relevance guard、批量预览缓存边界、`search_media.py` 局部瘦身和文档真相，没有改 downloader dispatch、approval、import 或 metadata 主链协议。
- 当前成人 BT 主线的两条真实 smoke 继续保持通过态；当前更需要留意的是：
  - 当前 BT 只读候选相关性保护已经收口：helper 相关性会在 `bt搜` top-N、`bt批量` default/selected selection 和 chat cache 顺序前统一生效，focused tests 已覆盖默认预览、定点预览和缓存边界
  - 如果后续仍出现边界噪声，只能继续收窄 helper 介入时机或只读截断策略；不能把 helper 结果写进审批真相，也不要再把 `search_media.py` 往上堆

## Latest verification

- `make quality`：`28 passed, 0 skipped`
- `make verify-mainline`：当前轮已通过
- focused pytest：
  - `tests/test_search_media.py tests/test_private_chat_bt_read_only_runtime.py tests/test_pure_bt.py tests/test_adult_content.py`：`209 passed, 0 skipped`
  - `.venv/bin/python -m pyflakes app/services/search_media.py app/services/bt_read_only_helper_selection.py`：通过
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

- 当前最大不确定性已经从“BT 只读排序 / 展示会不会被来源别名、噪声标题和重复历史提示拖乱”收敛到“后续是否还有必要继续收窄 helper 介入时机 / 只读截断策略，以及怎样继续保持 read-only、focused 且不引入新的 helper 真相边界”。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

保持质量硬化，不新增用户可感知功能。BT 只读候选相关性保护已收口；若继续推进，只沿着“BT 只读 helper 介入时机 / 只读截断策略继续收窄”做更窄的 focused tests / guard，不放宽成自动 dispatch 来源。
```
