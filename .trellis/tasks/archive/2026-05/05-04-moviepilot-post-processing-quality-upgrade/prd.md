# brainstorm: moviepilot post-processing quality upgrade

## Goal

把观影 PT 主链的导入后产物，从“基础链路能跑通”提升到接近 MoviePilot 的成品质量：

- 目录结构更像媒体库成品，而不是 release 文件平铺
- 命名优先使用已确认的媒体身份，尽量中文化
- metadata / NFO 不再只有最小 identity 字段
- 海报 / 背景图真实样本上稳定落盘
- 演员中文名 / 角色名进入 metadata truth
- 头像继续 `TMDB-first`
- 当 TMDB 本地化不足时，用 AI 做演员名 / 角色名中文化补充
- 中文字幕输出需要成品化：
  - 中文在上
  - 英文在下（小字）
  - 对照双排
  - 中文字体优先 `LXGW WenKai` / `LxgwWenKai`
  - 目标优先生成可样式化 ASS/SSA 成品字幕

## What I already know

* 自动化主链已推进：
  - 选 PT 资源后自动下载
  - 下载完成后自动导入
  - 后处理聚合总结通知
  - 四渠道共享主链方向已锁定
* 字幕翻译已经在真实样本上跑通：
  - `/data/library/movies/Akron DDP2 H NZMA E264.zh.srt` 已生成
  - 结构完整，1183 个块与源字幕一致
* 当前真实样本 `Akron / 爱的进行时` 的刮削链路只是“基础可用”，还远没到 MoviePilot 水平：
  - 文件仍平铺在 `/data/library/movies/`
  - 文件名还是 `Akron DDP2 H NZMA E264.mkv`
  - `metadata.json` 只有最小 TMDB identity + subtitle trusted name map
  - `nfo` 只有 `title / originaltitle / year / tmdbid`
  - 当前真实样本没有落 poster / backdrop 文件
  - 当前没有 cast 列表、演员中文展示、演员头像产物
* 现有代码底座已存在：
  - `ImportPrepareState` 已开始优先用 confirmed media identity 命名
  - `MetadataScraperService` 已能写 metadata / NFO
  - 已有 fanart + TMDB poster fallback 代码
  - `TmdbClient.get_movie_credits/get_tv_credits` 已存在，但 `TmdbCreditPerson` 还没有头像字段


## Library Truth Model

The user-provided library structure says:

- File names are mixed Chinese/English and are not the single source of truth.
- The real media truth is the layered structure around NFO + poster/backdrop + video + subtitles.
- Movies are organized under `Movie/<片名> (<年份>)/`.
- TV and Anime are organized under `TV|Anime/<剧名> (<年份>)/Season N/`.
- NFO files are the authoritative metadata layer for movie / tvshow / season / episode.
- Poster / backdrop / banner / thumb / logo / clearlogo / clearart / disc / art assets are first-class outputs, not decoration.
- Subtitle files may be bilingual / mixed naming, but should still be treated as media assets, not the only truth source.

This task should align scraper outputs with that layered media model rather than trusting release-style basenames.

## Requirements

### R1. 成品级目录结构和命名

* 电影导入后优先形成稳定成品路径，而不是 release 名平铺。
* 命名优先级：
  1. 已确认中文标题
  2. 已确认 original title
  3. 最后才 fallback 到 release-derived normalization
* 目录 / 文件名应优先形如：
  - `中文名 (年份)/中文名 (年份).mkv`
  - 至少不能继续长期停留在 `Akron DDP2 H NZMA E264.mkv` 这种 release 风格

### R2. metadata / NFO 丰富化

* 在现有 TMDB identity 之外，尽量补齐：
  - overview
  - genres
  - rating / vote_average / vote_count
  - countries / studios（可得时）
  - cast truth
* NFO 要尽量更像 Emby / Jellyfin 友好的成品，而不是只有最小标题字段

### R3. 海报 / 背景图稳定落盘

* 对真实电影样本，若 TMDB / fanart 可得，poster / backdrop 应实际落地到媒体库
* fanart 无图时继续走 TMDB fallback
* 不要求一步覆盖所有媒体类型，但电影真实样本必须先打穿

### R4. 演员中文 / 角色名 AI 补充层

* 当前只把少量 `trusted_name_map` 提供给字幕翻译，这不够
* 需要把 cast truth 扩展成可被 metadata/NFO 使用的结构：
  - 演员中文名
  - original name
  - 角色名（中文优先）
* 新边界：
  - `TMDB` 继续作为唯一主源
  - 不再继续接入豆瓣或其他外部中文源
  - 当 `TMDB zh-CN credits / also_known_as` 不足时，允许 AI 对演员名 / 角色名做中文化补充
  - `TMDB` 仍保留 `original_name / original_character / order / profile_image_url` 真相
  - 演员头像继续 `TMDB-first`
* AI 补充层要求：
  - 只补 `localized_name / localized_character`
  - 失败必须 soft-fail，不阻断 metadata/NFO 主链
  - 演员名比角色名更保守；没把握时宁可保留原文，也不要乱造常用译名

### R5. 不打碎当前自动化主链

* 所有质量升级必须建立在当前自动下载 / 自动导入 / 后处理聚合通知之上
* 不能回退成用户需要重新确认下载/导入

### R6. 中文字幕双排样式成品化

* 字幕翻译链需要支持双排 bilingual 成品样式
* 目标视觉：
  - 中文主行
  - 英文副行
  - 英文小字
  - 可在播放器中直接显示成品效果
* 若技术上必须分输出格式，优先考虑：
  - 电影/剧集成品字幕使用 ASS/SSA 样式化输出
  - 保留一个可回退的纯文本 / SRT 路径，但默认优先样式化输出
* 字体策略：
  - 中文字体优先 `LXGW WenKai` / `LxgwWenKai`
  - 英文可使用同字体的小字号，或等效可读字体

## Acceptance Criteria

* [ ] 电影真实样本导入路径 / 目标文件名不再是原始 release 风格
* [ ] metadata JSON 明显厚于当前最小版本，至少包含 overview + 更多 TMDB 字段 + cast truth
* [ ] NFO 明显厚于当前最小版本，且可被 Emby/Jellyfin 更好消费
* [ ] 真实样本 poster / backdrop 在可得时实际落盘
* [ ] cast truth 至少包含演员中文名 / original name / 角色名
* [ ] `TMDB-first` 头像 truth 不回归
* [ ] 当 TMDB 本地化不足时，AI 补充层能为 cast truth 生成合理中文演员名 / 角色名，且失败不阻断主链
* [ ] 中文字幕能生成双排 bilingual 成品样式
* [ ] 中文字幕主字体优先使用 LXGW WenKai / LxgwWenKai
* [ ] 当前字幕翻译、自动导入、通知主链不回归
* [ ] 中文字幕双排 ASS/SSA 成品样式可输出
* [ ] 中文字幕主字体优先使用 LXGW WenKai / LxgwWenKai

## Out of Scope

* 不一步复制 MoviePilot 全量生态能力
* 不重做成人 BT 归档语义
* 不再继续推进 Douban / 其他外部中文源 helper 接入
* 不为所有媒体服务器分别做定制化适配

## Technical Notes

* 主要涉及模块：
  - `app/services/import_prepare_state.py`
  - `app/services/import_to_library.py`
  - `app/services/import_transfer_execution.py`
  - `app/services/metadata_scraper.py`
  - `app/clients/tmdb.py`
  - （新增）AI cast localization service
* 参考计划：
  - `docs/plans/2026-05-03-telegram-automation-after-explicit-selection.md`
* 真实样本证据：
  - `Akron DDP2 H NZMA E264.*`
* 研究结论：
  - `research/domestic-enrichment-sources.md`
  - `research/moviepilot-douban-core-trace.md`
  - `research/moviepilot-douban-api-feasibility.md`
  - 外部中文源路线可研究，但当前实施方向改为 `TMDB 主源 + AI cast localization`
