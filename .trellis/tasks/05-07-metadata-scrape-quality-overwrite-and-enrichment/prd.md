# PRD — metadata scrape quality overwrite and enrichment

## Goal

提升导入后 metadata scraping 的最终落地产物质量，避免媒体库继续消费下载源自带的 release NFO，并把当前 TMDB/Fanart 已经可获得的高价值字段尽量完整写入 metadata sidecar / NFO / 图片工件。

## Current problems

- 目录型导入会把下载源自带的 `.nfo` 一起带进库目录。
- `MetadataScraperService` 对 NFO / 图片当前采用 `missing_only` 策略，导致已有 release NFO 时不会覆盖。
- 结果是媒体库优先读到 scene/release NFO，而不是 TMDB movie XML NFO。
- 即使写入了我们自己的 NFO，当前字段仍不够满，缺少 runtime、release date、tagline、director / writer 等高价值信息。

## Required behavior

1. metadata sidecar 继续覆盖写入。
2. NFO 改为覆盖写入，不允许旧 release NFO 阻止媒体 NFO落地。
3. poster / backdrop 也改为覆盖写入，避免旧错误图片长期残留。
4. 在现有 TMDB detail / credits 已可提供的范围内，补齐更多字段到 metadata sidecar 和 NFO：
   - runtime / release_date / tagline
   - directors / writers / crew-derived fields when available
   - richer cast / role truth
5. 不为了“字段更满”引入新的外部 provider 或新的持久化表。

## Explicit scope decisions

- 只处理当前 import-time metadata 产物质量，不改 Telegram 候选卡、不改字幕 provider、不改媒体服务器 refresh 协议。
- 不改 `SubtitleTranslatorService` 的 provider 路由，只保留与 metadata sidecar 字段衔接所需的兼容性。
- 不做新的 Web metadata helper / scraper source。

## Verification

- focused tests 保护：
  - 目录型导入时，已有 release NFO 也会被媒体 NFO 覆盖
  - 目录型导入时，已有 poster / backdrop 也会按新抓取结果覆盖
  - metadata sidecar / NFO 写出 runtime / release_date / tagline / directors / writers 等新增字段
- 跑 `tests/test_metadata_scraper.py`
