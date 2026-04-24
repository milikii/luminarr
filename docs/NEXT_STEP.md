# Next step (v346)

## Current goal

- **质量硬化**、**搜索相关性优化** 与 **字幕闭环补齐** 当前都已完成；默认分支若继续推进，当前唯一主线切到 **刮削系统基础收口**。
- 这条主线当前不改发布矩阵、不扩协议，只先收口一个基础事实：导入后刮削必须优先消费已确认媒体身份，而不是默认靠文件名重新猜片。
- 当前第一条最小闭环是：**把 `media_identity` 沿着 `search -> select -> confirm download -> job_event -> import metadata` 落成真相链**。
- 当前详细判断与分阶段设计见：`docs/SCRAPING_SYSTEM_PLAN.md`。
- 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态：`app/bot/private_chat_runtime.py` 当前 `467` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退。

## User value

- 这一步完成后，导入后的 metadata 刮削不再优先赌“文件名猜得对不对”，而是优先吃搜索确认时已经拿到的媒体身份真相。
- 这能直接降低后续 `.metadata.json`、`.nfo`、本地海报背景图围绕错误媒体对象展开的风险。
- 当前这条主线仍然只服务 movie-first，不把项目带进“大媒体管理平台”。

## Only do

- 只做刮削系统 Phase 1：
  - 搜索候选挂上 `media_identity`
  - 待确认下载 payload 保留 `media_identity`
  - 下载成功后写独立 `media.identity.confirmed` 事件
  - metadata 入参优先消费这份真相
- 继续保持 movie-first，不扩 TV / anime 本地刮削。
- 若默认分支重新出现红灯，只做首版承诺范围内最小修复。

## Do not do

- 不改发布矩阵，不重开真实 smoke 范围，不顺手把环境探针再写成产品承诺。
- 不先做全量 NFO / 图片体系，不先做 TV / season / episode 刮削，不先做全库扫描。
- 不改 SQLite schema，不改 approval / jobs / lease / downloader / import 副作用边界。
- 不把这条主线扩成多源元数据平台，不顺手引入 Douban / Bangumi / TVDB 或插件化 provider。

## Done when

当前 **刮削系统基础收口** 主线继续推进时，第一条最小闭环应满足：

1. 已确认的 `media_identity` 能从搜索候选带进下载确认，并在下载成功后以独立 `job_event` 落盘。
2. metadata 入参解析当前优先吃 `media_identity`，没有这份真相时才回退命名真相或文件名解析。
3. add/import/search focused tests 当前可通过，且 `make quality` 不回退。
4. `docs/STATUS.md`、本文件和 `docs/SCRAPING_SYSTEM_PLAN.md` 能把“当前第一步做了什么”写成当前真相。

## After this step

1. 让 `metadata_scraper` 直接优先吃 `tmdb_id`，停止二次 `search_movie(title, year)`。
2. 在 `.metadata.json` 之外补最小本地刮削产物：`.nfo`、`poster`、`backdrop`。
3. 再补 `missing-only / overwrite / skip` 写入策略与一次真实 `import -> scrape -> subtitle -> refresh` smoke。
