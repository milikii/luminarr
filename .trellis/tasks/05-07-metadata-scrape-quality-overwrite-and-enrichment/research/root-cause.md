# Root cause — metadata scrape quality regression

## Observed evidence

- `功夫熊猫 (2008)` 的 `.luminarr.metadata.json` 含有完整 TMDB truth、cast、poster/backdrop URL。
- 但库目录中的 `.nfo` 仍是下载源自带的 release / scene NFO，不是 XML `<movie>` NFO。
- `爱的进行时 (2015)` 已经落成 XML movie NFO，说明 metadata scraper 主链可工作，但字段仍偏少。

## Root cause

1. 目录型导入会把下载源目录整体硬链接 / 复制进库目录。
2. 源目录里的 release `.nfo` 会一起进入库目录。
3. `MetadataScraperService.scrape_for_import()` 在写 `nfo_path` 和图片工件时使用 `missing_only`。
4. 所以已有 release NFO / 旧 poster/backdrop 时，metadata scraper 不会覆盖。
5. 媒体库最终消费的是旧 release NFO，而不是当前 TMDB/Fanart 真相。

## Fix direction

- 对 metadata sidecar 维持 overwrite。
- 对 NFO / poster / backdrop 也改为 overwrite。
- 同时扩展 `TmdbMovie` 与 `metadata_scraper` 输出字段，把 detail endpoint 已有真相尽量完整落地到工件。
