# Next step (v349)

## Current goal

- **质量硬化**、**搜索相关性优化** 与 **字幕闭环补齐** 当前都已完成；默认分支若继续推进，当前唯一主线切到 **刮削系统基础收口**。
- 这条主线当前不改发布矩阵、不扩协议，只先收口一个基础事实：导入后刮削必须优先消费已确认媒体身份，而不是默认靠文件名重新猜片。
- 当前刚完成的最小闭环是：**最小本地图片产物 `poster` / `backdrop` 已开始落地**。
- 当前详细判断与分阶段设计见：`docs/SCRAPING_SYSTEM_PLAN.md`。
- 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态：`app/bot/private_chat_runtime.py` 当前 `467` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退。

## User value

- 导入后的 metadata 刮削现在不再优先赌“文件名猜得对不对”，而是优先吃搜索确认时已经拿到的媒体身份真相。
- 只要 `media_identity` 里已经有 `tmdb_id`，metadata 刮削现在会直接按该 ID 取详情，不再重新拿 `title/year` 搜一次。
- 当前又把本地刮削产物前推了一步：`.metadata.json` 之外不仅已有 `.nfo`，也已经开始生成本地 `poster` / `backdrop` 文件，媒体服务器可消费的本地真相不再只有内部 sidecar。
- 当前这条主线仍然只服务 movie-first，不把项目带进“大媒体管理平台”。

## Only do

- 继续做刮削系统 Phase 3：
  - 在 `.metadata.json` / `.nfo` / `poster` / `backdrop` 都已开始落地的基础上补写入策略
  - 先明确 `missing-only / overwrite / skip`
  - 不把这一步扩成全量图片下载系统
- 继续保持 movie-first，不扩 TV / anime 本地刮削。
- 若默认分支重新出现红灯，只做首版承诺范围内最小修复。

## Do not do

- 不改发布矩阵，不重开真实 smoke 范围，不顺手把环境探针再写成产品承诺。
- 不先做全量 NFO / 图片体系，不先做 TV / season / episode 刮削，不先做全库扫描。
- 不改 SQLite schema，不改 approval / jobs / lease / downloader / import 副作用边界。
- 不把这条主线扩成多源元数据平台，不顺手引入 Douban / Bangumi / TVDB 或插件化 provider。

## Done when

当前 **刮削系统基础收口** 主线继续推进时，下一条最小闭环应满足：

1. `.metadata.json` / `.nfo` / 图片的写入策略已经明确，不再全靠当前默认覆盖语义。
2. 写入策略不破坏现有 import / subtitle / refresh 真相链。
3. add/import/metadata focused tests 当前可通过，且 `make quality` 不回退。
4. `docs/STATUS.md`、本文件和 `docs/SCRAPING_SYSTEM_PLAN.md` 能把“当前下一步做到哪层策略”写成当前真相。

## After this step

1. 补 `missing-only / overwrite / skip` 写入策略。
2. 再补一次真实 `import -> scrape -> subtitle -> refresh` smoke。
3. 如果真实 smoke 仍稳定，再决定是否继续补更多图片类型。
