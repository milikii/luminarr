# Current status (v480)

## Current mainline

- **质量硬化** 当前保持完成态，不回退。
- 当前默认分支主线切到 **验证入口收口 / 操作文档瘦身**；详细蓝图统一看 `docs/VERIFICATION_ENTRYPOINTS_PLAN.md`。
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
  - `bt搜` / `bt批量` 当前不会因为只剩单个候选或用户显式选中无关项就兜底贴 helper；无关候选继续保持 helper-free 展示与缓存
  - helper title overlap 当前会过滤 `collection / compilation / edition / complete` 这类泛噪声 token，减少 generic overlap 把无关标题误判成相关候选
  - 成人 BT 下载完成后可进入归档，统一保留窗口到期后可清理下载器任务与源资源
  - direct magnet 运行时选择 `BT 成人链` 时，已能直接创建成人磁力下载待确认并尽量识别番号 / 分类
  - qB 导入源解析已改成优先使用真实 `content_path`，不再盲信漂移的 `save_path`
  - `DOWNLOADER_INSTANCES` 当前可选第 5 段 `dispatch_download_dir`；容器化下载器可把“下载器 API 投递路径”和“宿主机导入路径”分开表达
  - 路由层当前会在导入查询时优先恢复任务真相里的 host `download_dir`，不再把 Transmission RPC 的容器路径直接喂给归档/导入
  - qB 成人归档真实 smoke 已通过：归档成功、保留期清理成功、`adult_content_registry` 最终为 `archived_deleted`
  - BT Transmission 成人归档真实 smoke 已通过：归档成功、保留期清理成功、`adult_content_registry` 最终为 `archived_deleted`
- 当前热点大文件仍需留意：`app/services/search_media.py` `627` 行，`add_to_downloader.py` `606` 行，`import_to_library.py` `590` 行；BT 只读展示逻辑现在已抽到 `app/services/bt_read_only_display.py` `180` 行，BT 只读 helper relevance 选择仍位于 `app/services/bt_read_only_helper_selection.py` `104` 行，未改对外协议。
- BT 来源适配当前保持：
  - 成人站点优先：`tokyotosho` / `sukebei(offkab)` / `javbus`
  - `Prowlarr` 成人 PT 作为补充来源
  - `javlibrary` 当前定位已经收口为 **BT-only read-only exact-id helper**，不放宽成自动 dispatch 来源

## Current health

- 当前这轮代码真相已经把 `search_media.py` 和 `import_to_library.py` 再收了一截；下一条风险更集中在：
  - `Makefile` 的公开验证入口仍然过碎，操作者层很难一眼看出“该跑哪组验证”
  - `docs/OPERATOR_RUNBOOK.md` 仍有过时主线残留和重复提示，文档入口比当前代码主线更难读
  - 下一线程若不先收这两个入口，后续继续推进会更依赖人肉判断而不是文档自解释

## Later candidate line

- 当前唯一执行主线不变；若后续显式切到“消息展示体验层”，统一蓝图看 `docs/SEARCH_REPLY_PRESENTATION_PLAN.md`。
- 这条后续候选主线固定为 `Telegram-first`：先做 Telegram richer reply，Feishu / personal WeChat / WeCom 首阶段先保留共享文本降级，不改 shared runtime / approval / dispatch 真相。
- 成人 BT 图片目标当前记为“尽量全量带图”，但实施分阶段：先 exact-id 与稳定只读图源，再扩到泛关键词结果；拿不到稳定图源时明确降级为纯文本。

## Latest verification

- `make quality`：`28 passed, 0 skipped`
- `make verify-mainline`：当前轮已通过
- focused pytest：
  - `tests/test_bt_read_only_helper_selection.py tests/test_search_media.py tests/test_private_chat_bt_read_only_runtime.py tests/test_pure_bt.py`：`204 passed, 4 warnings`
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

- 当前最大不确定性已经进一步收敛到“后续是否还会出现 helper title overlap 只靠更边缘 token 误命中的个案，以及是否还需要继续收窄只读截断策略”；若继续推进，也只能继续做更窄的 focused tests / guard，不能放宽 helper 真相边界。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

这轮主线只做“验证入口收口 / 操作文档瘦身”：先收 Makefile 的 verify-mainline / cleanup 公开入口，再收 docs/OPERATOR_RUNBOOK.md 和相关入口文档；不改业务协议，不删 approval / lease / version / confirm / recovery 边界。
```
