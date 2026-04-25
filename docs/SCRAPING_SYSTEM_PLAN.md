# Scraping System Plan (v1)

## Goal

把当前 movie-first 导入链里的 metadata 收口成一个真正可维护的刮削系统。

这条主线当前不追求“一次做全 MoviePilot”，只追求：

1. 已确认媒体身份能沿着主链稳定落到导入后处理
2. 刮削阶段不再默认靠文件名重新猜片
3. 后续产物（`.metadata.json` / `.nfo` / 图片）有清晰分层

## Reference Judgment

参考 MoviePilot 之后，当前对 Luminarr 的判断是：

- 值得学的是：
  - 先识别，再刮削
  - 刮削产物按类型管理
  - 写文件有明确策略（missing-only / overwrite / skip）
- 不该照搬的是：
  - 一次上全量 TV / season / episode 刮削
  - 全库扫描与大后台任务
  - 多站点、多元数据源平台化

Luminarr 当前仍是：

- single instance / single process / single host
- movie-first
- 导入后闭环优先

所以刮削系统必须服务这条主链，而不是反过来把项目拖进“大媒体管理平台”。

## Current Gap

当前仓库里的 metadata 还很薄：

- `app/services/metadata_scraper.py` 只是用 `title/year` 再查一次 TMDB，然后补一点 Fanart，最后写 `.metadata.json`
- 这份 `.metadata.json` 更像内部 sidecar，不是成熟意义上的本地刮削产物系统
- 最大问题不是“图片不够多”，而是“导入后还在重新猜片”

## Design Rules

### 1. `media_identity` 是刮削输入真相

刮削阶段优先消费搜索/确认阶段已经确认过的媒体身份，而不是重新靠文件名模糊识别。

当前最小结构：

- `media_type`
- `tmdb_id`
- `title`
- `original_title`
- `year`
- `source`

### 2. 内部真相和对外产物分开

当前与后续的刮削产物分四层：

1. 内部真相：
   `.luminarr.metadata.json`
2. 媒体服务器可读元数据：
   `movie.nfo` 或 `<basename>.nfo`
3. 图片：
   `poster` / `backdrop`
4. 执行记录：
   `job_event`

### 3. 先做 movie-first

当前不提前做：

- TV / season / episode NFO
- 动漫命名兼容刮削
- 全库扫描补刮削

## Rollout

### Phase 1

目标：先把 `media_identity` 沿着当前主链落稳。

当前状态：已完成

最小实现：

- 搜索候选写入时附带 `media_identity`
- `select -> confirm download` 的 pending payload 保留 `media_identity`
- 下载成功后把 `media_identity` 作为独立 `job_event` 落盘
- 导入侧 metadata 入参优先吃这份真相，不再先靠文件名猜片

### Phase 2

目标：让 `metadata_scraper` 直接优先吃 `tmdb_id`。

当前状态：已完成

最小实现：

- `MetadataScrapeInput` 增加可选 `tmdb_id`
- 有已确认 `tmdb_id` 时，不再走 `search_movie(title, year)`，改成直接取对应详情
- detail 查询当前固定使用 `zh-CN`
- 若拿不到中文标题，当前刮削会 fail-closed，不再把英文标题悄悄落进最终产物

### Phase 3

目标：产出真正的本地刮削产物。

当前状态：已完成；`.luminarr.metadata.json`、`.nfo`、`poster`、`backdrop` 已落地，写入策略与真实 smoke 见 Phase 4

最小实现：

- 保留 `.luminarr.metadata.json`
- 新增 `.nfo`（已完成）
- 新增 `poster` / `backdrop`（已完成）

### Phase 4

目标：明确写入策略与真实验证。

当前状态：已完成

最小实现：

- `.metadata.json`：`overwrite`（已完成）
- `.nfo` / 图片：先 `missing-only`（已完成）
- 补一次真实 `import -> scrape -> subtitle -> refresh` smoke（已完成）

## Later structural backlog

这些不是当前刮削主线的即时 blocker，但已经明确挂进后续任务，避免再次靠口头记忆：

- `app/services/subtitle_translator.py`
  - 当前状态：已再前推几格；support helper 已承接目标字幕解析、chunk 翻译编排、异常校验、`ffprobe/ffmpeg` subprocess 执行编排、“可提取英文内嵌字幕结果筛选”、“提取后字幕文件可用性整理”、“单文件翻译读写边界”、翻译请求载荷构造、专业翻译请求执行 / 响应解析 / 错误映射、SRT / ASS 渲染编排、`translate_for_import` 的 skip/success 结果构造、`_translate_single_file` / `_extract_embedded_subtitle_file` 的失败结果构造，以及“外挂字幕识别 + 中文字幕外挂 skip 优先级”“内嵌字幕流优先级判定”“ffprobe 结果解析 / 错误映射”“提取结果解析 / 半成品清理”“ffmpeg fallback 结果解析 / 错误映射”；当前 `subtitle_translator.py` 为 `283` 行。
  - 目标：继续按“前置校验 / 剩余结果封装 / 中文跳过策略”收口剩余编排
- `app/services/manage_bt_subscription.py`
  - 当前状态：已再前推几格；CRUD 持久化 guard、扫描前的 `chat_ids/items` 读取护栏、`last_seen` 回写护栏，以及单条订阅的搜索 / pending 创建编排都已下沉到 `bt_subscription_repo_support.py` / `bt_subscription_dispatch_support.py`；当前 `manage_bt_subscription.py` 为 `900` 行。
  - 目标：继续按“命令解析 / scheduler tick 总编排 / 剩余结果封装”拆分
- `app/services/cleanup_downloaded_source.py`
  - 当前状态：已再前推几格；命令解析、`job_event` 追加护栏、inspection 计算、inspect 文本渲染、follow-up / blocked outcome 编排、删除执行、PT seed guard 评估、blocked / event / delete failure 日志，以及 cleanup 主流程编排都已下沉到 `cleanup_query_support.py` / `cleanup_event_support.py` / `cleanup_inspection_support.py` / `cleanup_inspect_render_support.py` / `cleanup_follow_up_support.py` / `cleanup_blocked_support.py` / `cleanup_execution_support.py` / `cleanup_seed_guard_support.py` / `cleanup_logging_support.py` / `cleanup_flow_support.py`；当前 `cleanup_downloaded_source.py` 为 `340` 行。
  - 当前补充：`inspect_by_task_ref()` 主流程、`cleanup_correlation_lookup.py` 的关联事件读取护栏、主流程、路径缺失判定 / 结果构造、任务身份解析，以及 cleanup 路径校验 / 删除资产也已继续下沉到 `cleanup_inspect_flow_support.py` / `cleanup_correlation_event_support.py` / `cleanup_correlation_flow_support.py` / `cleanup_correlation_result_support.py` / `cleanup_task_identity_support.py` / `cleanup_correlation_logging_support.py` / `cleanup_path_guard_support.py` / `cleanup_asset_support.py`；当前 `cleanup_downloaded_source.py` 为 `334` 行，`cleanup_correlation_lookup.py` 为 `215` 行。
  - 目标：继续按“剩余 service 粘合层 / correlation lookup 最后封装层”拆分
- `app/db/approval_repo.py`
  - 当前状态：已再前推几格；任务身份校验、approval 行查询、状态更新、executed/move 写入，以及读路径后处理都已下沉到 `approval_repo_support.py`；当前 `approval_repo.py` 为 `779` 行。
  - 目标：继续按“action 族入口 / 剩余 SQL 写入边界”收口
- `app/db/job_repo.py`
  - 目标：按 workflow/job lifecycle 的 query/update helper 收口，降低跨能力族耦合

这些文件的拆解默认排在当前刮削主线之后；只有当其中某个文件直接阻塞当前 `media_identity -> scrape` 主线时，才允许提前插队。

## Not Now

当前不做：

- schema 级大改
- 全库重刷
- 插件化刮削 provider
- Douban / Bangumi / TVDB 多源融合
- TV / anime 全量本地刮削
