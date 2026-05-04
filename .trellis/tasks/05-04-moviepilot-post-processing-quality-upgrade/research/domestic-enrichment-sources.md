# Research: domestic-enrichment-sources

- Query: 在不替代 TMDB 主源的前提下，用豆瓣或其他国内来源补充 `演员中文名 / 角色中文名 / 演员头像` 是否可行，最稳的接入边界是什么
- Scope: mixed
- Date: 2026-05-04

## Findings

### Direct answer

可行，但最稳的做法不是把国内源变成第二主源，而是做成 `TMDB identity + 国内 helper enrichment`：

- 第一阶段只建议补 `演员中文名` 和 `角色中文名`
- `演员头像` 继续以 TMDB 为唯一成品源；国内源头像最多只保留为低信任候选 URL，不进 NFO 主字段、不默认下载
- 国内源只在 `tmdb_id` 已确认、TMDB credits 已拿到之后运行，失败必须软降级回 TMDB-only

### Files found

- `.trellis/tasks/05-04-moviepilot-post-processing-quality-upgrade/prd.md`
  - 当前 task 已把“演员中文名 / 角色名 / 头像 truth”列为明确目标与验收项
- `app/clients/tmdb.py`
  - 当前 TMDB client 已有 credits 获取与 `profile_path` 字段
- `app/services/metadata_scraper.py`
  - 当前 metadata/NFO 已由 TMDB credits 生成 cast truth，并把头像 URL 写入 NFO `<actor><thumb>`
- `.trellis/spec/backend/bt-source-contracts.md`
  - 项目已有成熟的“主源 vs helper_only enrichment”边界可复用到国内 metadata enrichment

### Code patterns

- 现有 cast truth 完全由 TMDB credits 构建：
  - `MetadataScraperService` 先拉 `localized_credits` / `reference_credits`，再生成 `cast_truth` 并写入 metadata/NFO
  - 见 `app/services/metadata_scraper.py:136-170`, `app/services/metadata_scraper.py:220-235`
- 当前 cast truth 已包含头像字段，且 NFO 会直接消费：
  - `profile_path` / `profile_image_url`
  - 见 `app/services/metadata_scraper.py:603-616`
- 当前 TMDB client 已支持语言参数与 credits 人物头像字段：
  - `TmdbCreditPerson.profile_path`
  - `get_movie_credits(..., language=...)`
  - 见 `app/clients/tmdb.py:50-60`, `app/clients/tmdb.py:106-116`, `app/clients/tmdb.py:280-322`, `app/clients/tmdb.py:420-436`
- 项目已有 helper enrichment 边界先例：
  - helper 可以 enrich 展示/元数据，但不能升级为 default main source
  - helper 失败必须 fall through / fail soft
  - 演员名等高风险字段不能机器瞎翻
  - 见 `.trellis/spec/backend/bt-source-contracts.md:141-152`, `.trellis/spec/backend/bt-source-contracts.md:173-181`, `.trellis/spec/backend/bt-source-contracts.md:199-203`

### External references

- TMDB 官方语言文档明确写了：TMDB 大多数元数据支持本地化，但 `person names` 和 `characters` 仍是主要缺口
  - https://developer.themoviedb.org/docs/languages
- TMDB 官方 credits endpoint 支持 `language` 参数，现有代码已经在用 `zh-CN` 和 `en-US`
  - https://developer.themoviedb.org/reference/movie-credits
- TMDB 官方 external IDs endpoint 可作为国内源 subject 匹配校验锚点
  - https://developer.themoviedb.org/reference/movie-external-ids
  - https://developer.themoviedb.org/reference/tv-series-external-ids
- 豆瓣电影 subject 页对通用电影/剧集的中文 enrichment 价值很高：
  - subject 页直接给出中文演员名、IMDb 编号
  - 演职员区给出“演员中文名 + 角色中文名/原名”
  - 示例：`盗梦空间`
  - https://movie.douban.com/subject/3541415/?dt_dapp=1
- 但豆瓣的自动化接入稳定性明显偏弱：
  - subject 的“全部演职员”页会被跳转到 `sec.douban.com`
  - 演员 personage 页在自动抓取下直接返回 `403`
  - 这说明它适合作为 best-effort helper，不适合作为生产主链硬依赖
- 豆瓣法务/使用约束风险高：
  - 官方法律声明把“通过 API 接入等形式使用豆瓣数据”纳入声明范围
  - 未经书面许可，不得抓取、采集、摘录或衍生利用豆瓣内容/数据
  - https://www.douban.com/about/legal
- 其他国内源里，只有 Bangumi 值得保留为 anime-only 例外：
  - 它至少有公开 API/规范仓库，且 schema 里有 `name_cn` / `images`
  - 但域模型明显偏 ACG，不适合作为通用 movie/tv 国内 enrichment 主方案
  - https://github.com/bangumi/api
  - https://raw.githubusercontent.com/bangumi/api/master/open-api/v0.yaml

### Source assessment for this task

| Source | 适合做 enrichment | 不适合做主源的原因 | 对本任务的结论 |
|---|---|---|---|
| Douban subject/celebrities | 是 | 无稳定公开授权 API；反爬明显；法律声明严格；页面结构和可访问性可能波动 | 只适合做 helper-only 中文文本补充 |
| Bangumi | 仅 anime 特例 | 域覆盖偏 ACG，不是通用电影/剧集库 | 本轮先不纳入通用实现 |
| 其他国内电影站 | 不建议 | 通常没有比豆瓣更强的通用演员/角色结构化覆盖，也没有更清晰的官方接入契约 | 不值得进入本轮方案 |

### Data coverage judgment

#### 1. 演员中文名

- 豆瓣可行性：高
- 原因：
  - subject 页“主演”直接给出中文演员名
  - 演职员区通常也以中文演员名展示
- 风险：
  - 全量 cast 覆盖不一定稳定，主角优先、长尾会掉
  - 人物页 `403` 说明不要把“按演员单独查中文名”作为主路径

结论：`演员中文名` 是国内 enrichment 最值得补、也最容易落地的字段。

#### 2. 角色中文名

- 豆瓣可行性：中高
- 原因：
  - 演职员区直接有 `饰 柯布 Cobb` 这类“中文角色名 + 原名”展示
- 风险：
  - subject 首屏通常只给前几位主角，完整演职员页又更容易触发风控
  - TV/长尾 cast 的角色覆盖会比电影首屏更不稳

结论：`角色中文名` 可补，但应只对前 N 位 cast 做 best-effort，不应把全量覆盖当成硬承诺。

#### 3. 演员头像

- 豆瓣可行性：技术上可尝试，工程上不稳
- 原因：
  - 演职员/人物页确实有头像资源
- 风险：
  - 访问人页 `403`，全量演职员页跳安全页，说明头像抓取路径最容易断
  - 头像涉及图片授权/缓存/热链风险，法务压力高于纯文本字段
  - 当前代码已经能从 TMDB 拿 `profile_path`，头像主链并不缺来源，只缺覆盖率

结论：`演员头像` 不应该是第一阶段的国内 enrichment 目标；最稳边界是继续 TMDB-first，只把国内头像当作将来可选 fallback URL。

### Recommended implementation boundary

#### Recommended responsibility split

- TMDB 主源负责：
  - `tmdb_id`
  - `media_type`
  - 标题、年份、overview、genres、countries、studios
  - cast 排序、`person_id`
  - `original_name`
  - 默认 `profile_path` / `profile_image_url`
- 国内 enrichment 层只负责：
  - `localized_name` 或补强 `name`
  - `localized_character` 或补强 `character`
  - 可选 `domestic_profile_image_url` 候选值
  - provenance / confidence / source URL

#### Most stable integration point

最稳的接入点不是改 TMDB client，而是在 `MetadataScraperService` 里把国内源做成一个后置 enrichment 步骤：

1. 先按现有路径拿到 TMDB detail + credits
2. 先构造 TMDB-based `cast_truth`
3. 再用一个 `DomesticCastEnrichmentService` 对 `cast_truth` 做 best-effort merge
4. 只补空缺或提高本地化展示质量，不改 identity truth
5. merge 失败时直接回落到原始 `cast_truth`

这样能保持：

- `app/clients/tmdb.py` 不被国内源耦合污染
- 现有字幕翻译 trusted name map 逻辑仍可继续以 TMDB 为底
- metadata/NFO 写入层只消费统一的 cast truth 结构

#### Matching strategy

- subject 匹配优先级：
  1. `TMDB external_ids -> IMDb ID` 作为校验锚点
  2. 国内源返回的 subject 必须能反查到同一 IMDb，才算高置信
  3. 若没有 IMDb，再退到严格 `title/original_title + year` 校验
- person/cast 匹配优先级：
  1. 在已确认的 subject 内，按 billed order + `original_name` 对齐 TMDB cast
  2. 不做“先搜国内演员页再反推作品”的反向主流程

#### Override rules

- 可以覆盖：
  - `name`，仅当 TMDB 名称不含 CJK 且国内源给出高置信中文名
  - `character`，仅当国内源给出高置信中文角色名
- 不可以覆盖：
  - `id`
  - `original_name`
  - `original_character`
  - `order`
  - `profile_path`
- 头像规则：
  - `profile_image_url` 继续指向 TMDB
  - 国内头像若要保留，只新增 `domestic_profile_image_url`
  - 第一阶段不要把国内头像写进 NFO `<thumb>`

#### Operational guardrails

- helper-only + fail-soft
- 默认只 enrich 前 `10-20` 位 cast
- 强制缓存，避免频繁触发国内站风控
- 超时短、禁止阻塞导入主链
- 记录字段级 provenance，例如：
  - `name_source=tmdb|douban`
  - `character_source=tmdb|douban`
  - `match_confidence=imdb_verified|title_year_verified|weak`

### Final recommendation for this task

如果目标是“直接服务当前实现”，推荐落地顺序应是：

1. 先做 `TMDB 主源 + 豆瓣 helper-only 文本 enrichment`
   - 只补 `演员中文名`
   - 次补 `角色中文名`
2. 头像仍然只走 TMDB 成品链
3. 国内头像只保留为未来开关项，不进入本轮验收

这样既能明显提升 Emby/Jellyfin 中文观感，又不会把后处理主链绑死在一个高反爬、高法务风险的数据源上。

## Caveats / Not Found

- 当前 Trellis active-task 指针是空的；本次按用户明确指定的 task 目录写入研究文件，而不是依赖 `task.py current`。
- 本次没有找到豆瓣当前可公开依赖、面向第三方产品的稳定电影数据 API；结论基于其公开页面形态、可访问性表现和官方法律声明。
- 没有去做“大量国内站点横评”，因为当前问题的实现价值集中在“能否形成稳边界”；结论是除了 Douban 的中文文本补充价值外，其余通用国内源不值得在本轮引入。
