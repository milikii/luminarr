# Next step (v351)

## Current goal

- **质量硬化**、**搜索相关性优化**、**字幕闭环补齐** 与 **刮削系统基础收口** 当前都已完成。
- 当前这一条主线已经补齐到真实 smoke：`import -> scrape -> subtitle -> refresh` 已在真实 PT Transmission / Emby 环境复验通过。
- 当前详细判断与分阶段设计见：`docs/SCRAPING_SYSTEM_PLAN.md`。
- 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态：`app/bot/private_chat_runtime.py` 当前 `467` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退。

## User value

- 导入后的 metadata 刮削现在不再优先赌“文件名猜得对不对”，而是优先吃搜索确认时已经拿到的媒体身份真相。
- 只要 `media_identity` 里已经有 `tmdb_id`，metadata 刮削现在会直接按该 ID 取详情，不再重新拿 `title/year` 搜一次。
- 当前这条主线已经补到真实产物层：`.metadata.json`、`.nfo`、`poster`、`backdrop` 已落地，且 Emby 已能消费到 `Name=Interstellar`、`Tmdb=157336` 的结果。
- 当前默认策略已明确：
  - `.metadata.json`：`overwrite`
  - `.nfo`：`missing-only`
  - `poster` / `backdrop`：`missing-only`
  - 没有来源或当前不该写时：`skip`

## Only do

- 当前这条主线已可宣告完成；若继续推进，优先从 `docs/SCRAPING_SYSTEM_PLAN.md` 的后续 backlog 或新的 operator 指定主线里选更小闭环。

## Do not do

- 不把这条已完成主线再扩成全量 NFO / 图片体系，不顺手开 TV / season / episode、本地全库扫描、多源 provider。

## Done when

当前这条 **刮削系统基础收口** 主线已经满足：

1. `media_identity` 已沿着 `search -> select -> confirm download -> job_event -> import metadata` 落稳。
2. `metadata_scraper` 已优先吃 `tmdb_id`。
3. `.metadata.json`、`.nfo`、`poster`、`backdrop` 已开始落地，且写入策略已明确。
4. 真实 `import -> scrape -> subtitle -> refresh` smoke 已通过，Emby 侧已确认消费结果。

## After this step

1. 如果继续沿刮削方向推进，优先评估是否还要补更多图片类型或更严格的本地产物命名规则。
2. 如果继续按结构降本推进，优先回到 `docs/SCRAPING_SYSTEM_PLAN.md` 里的大文件 backlog。
