# Research: actor-name-alternative-sources

- Query: 如果只需要“演员中文名”，`Trakt / IMDb / Wikidata / Wikipedia` 这些公共来源里哪个最可行，为什么
- Scope: mixed
- Date: 2026-05-04

## Findings

### Direct answer

结论很明确：

1. `Wikidata/Wikipedia` 最可行，但应按 `Wikidata 主、Wikipedia 仅作 sitelink/校验补充` 使用
2. `IMDb` 只能做稳定对齐骨架，不适合作为“演员中文名”来源
3. `Trakt` 最不值得接，对“演员中文名”几乎没有新增价值

如果当前问题只有一个决策要做，我的推荐是：

- 只有在你要找“公开可用、能给演员中文名”的替代源时，才值得看 `Wikidata/Wikipedia`
- 其中真正该接的是 `Wikidata`
- `Wikipedia` 不应单独作为主源
- `IMDb` 和 `Trakt` 不建议为“演员中文名”单独接入

### Why this ranking

#### 1. Wikidata/Wikipedia

这是四者里唯一一个对“演员中文名”有现实价值的公共来源组。

- 是否有中文演员名：
  - `Wikidata` 的实体 JSON 原生就有多语言 `labels` / `aliases` / `descriptions` / `sitelinks`
  - 官方文档明确说明这些字段按语言组织，且 `wbgetentities` 可按指定语言返回，并支持 `languagefallback`
  - `Wikipedia` 也能提供中文页标题/摘要，但它更像展示层补充，不是稳定的结构化主键层
- 是否可通过 IMDb/英文名稳定对齐：
  - `Wikidata` 有 `P345 = IMDb ID` 属性，且属性页明确它适用于 `human`
  - `P345` 的属性页还标注了 `stability of property value = never changes`
  - 这意味着如果你已有 `IMDb person id`，对齐是稳定的
  - 若没有 IMDb，只靠英文名也能做，但可靠性会明显下降
- 是否公开可用：
  - `Wikidata` 有公开 `wbgetentities` API
  - 也有公开 `SPARQL` endpoint
  - `Wikipedia` / `MediaWiki` 侧也有公开 page/query API
- 工程复杂度：
  - 中等，不低，但可控
  - 真正的复杂点不在 API 可用性，而在“你当前链路里有没有稳定的人物外部 ID”
  - 当前项目的 helper seam 已经允许在 TMDB cast truth 之后做 best-effort merge，并按 `original_name` / `cast_id` / `order` 软合并，因此从架构上可接
  - 但如果没有每个演员的 IMDb person id，`Wikidata` 的最佳接法会退化成按英文名或按条目内 cast 顺序对齐，复杂度会上升

判断：

- `Wikidata` 值得接
- `Wikipedia` 只适合作为 `Wikidata sitelink` 的展示/兜底来源，不适合单独主接

#### 2. IMDb

`IMDb` 不是“演员中文名来源”，只能算“对齐基础设施”。

- 是否有中文演员名：
  - 官方非商业数据集中，人物侧公开字段是 `name.basics.tsv.gz`
  - 里面只有 `nconst`、`primaryName`、`birthYear`、`deathYear`、`primaryProfession`、`knownForTitles`
  - 与 title 侧不同，IMDb 官方公开数据并没有提供人物多语言名/中文别名结构
  - `title.akas.tsv.gz` 只覆盖 title 的本地化标题，不覆盖 person name
- 是否可通过 IMDb/英文名稳定对齐：
  - 很强，`nconst` 就是稳定的人物 ID
  - 但这解决的是“对齐”，不是“中文名”
- 是否公开可用：
  - 有官方 `Non-Commercial Datasets`，每日刷新，可下载本地副本
  - 但官方页面也明确是 `personal and non-commercial use`
  - 更进一步的数据商业化使用则需要联系 IMDb
- 工程复杂度：
  - 中等偏高
  - 你要自己拉取、解析、缓存数据
  - 但最终拿到的仍然主要是英文 `primaryName`

判断：

- 若目标只是“演员中文名”，IMDb 不值得单独接
- 它最多只该作为 `Wikidata` 或别的中文源的对齐锚点

#### 3. Trakt

`Trakt` 对这个问题基本没有现实价值，排最后。

- 是否有中文演员名：
  - 官方 person schema 公开字段本质上是单个 `name`，外加 `ids`、`biography`、`birthday`、`birthplace`、`gender`、`images`
  - 没有 `labels` / `aliases` / `translations` 这类多语言 person-name 契约
- 是否可通过 IMDb/英文名稳定对齐：
  - person payload 里确实会带 `ids.imdb` / `ids.tmdb`
  - 但 `people/:id` 路由的 `id` 官方契约写的是 `slug of the resource`
  - 也就是说它的人物读取不是天然 external-id first
  - 对我们来说，这比直接用 `IMDb` / `Wikidata P345` 更绕
- 是否公开可用：
  - API 是公开给第三方 app 用的
  - 但需要申请 `client id/secret`
  - 官方还提醒 public applications 可能有接口限制
- 工程复杂度：
  - 单看接 API 本身不高
  - 但它不提供我们真正缺的“演员中文名”，所以复杂度再低也没有意义

判断：

- 不建议为了“演员中文名”接 Trakt
- 它提供的增量远小于现有 `TMDB + helper-only enrichment` 架构已经具备的能力

### Files found

- `.trellis/tasks/05-04-moviepilot-post-processing-quality-upgrade/prd.md`
  - 当前 task 明确要求把 `演员中文名` 写入 cast truth
- `app/services/domestic_cast_enrichment.py`
  - 已经存在 helper-only 人物补全文本 seam，可复用给公共来源
- `app/services/metadata_scraper.py`
  - 当前 metadata/NFO 会消费 cast truth，且补全失败必须软降级
- `app/clients/douban_cast_helper.py`
  - 当前 helper 主要是 title/original_title/year 驱动，说明替代源若要更稳，最好能提供更强 person-level 锚点
- `.trellis/spec/backend/bt-source-contracts.md`
  - 项目已有 `helper_only` / `fail-soft` 合同，可直接复用到演员名补全来源

### Code patterns

- helper-only 输入里已经预留 `tmdb_id` 和完整 `cast_truth`：
  - `app/services/domestic_cast_enrichment.py:10-27`
- 当前 metadata 刮削在构建 TMDB cast truth 后，再做 helper-only merge：
  - `app/services/metadata_scraper.py:147-154`
- helper enrichment 失败必须记录并软降级回原始 TMDB-only cast truth：
  - `app/services/metadata_scraper.py:283-306`
- 当前 merge 锚点是 `cast_id`、`original_name`、`order`：
  - `app/services/metadata_scraper.py:309-337`
- 现有 Douban helper 仍是 title/original_title/year 驱动，不是 person external-id 驱动：
  - `app/clients/douban_cast_helper.py:50-61`
  - `app/clients/douban_cast_helper.py:119-177`

### External references

- Trakt 官方 API 仓库 README：API 面向第三方应用，需要 `TRAKT_CLIENT_ID` / `TRAKT_CLIENT_SECRET`；public applications 可能有限制
  - https://raw.githubusercontent.com/trakt/trakt-api/master/README.md
- Trakt people router：官方 people 路由只有 `summary` / `movies` / `shows`
  - https://raw.githubusercontent.com/trakt/trakt-api/master/projects/api/src/contracts/people/index.ts
- Trakt person schema：person 公开字段是 `name` + `ids` + biography/birthday/...，没有多语言 name 契约
  - https://raw.githubusercontent.com/trakt/trakt-api/master/projects/api/src/contracts/people/schema/response/personResponseSchema.ts
- Trakt id 参数：`people/:id` 的 `id` 官方说明是 `slug of the resource`
  - https://raw.githubusercontent.com/trakt/trakt-api/master/projects/api/src/contracts/_internal/request/idParamsSchema.ts
- IMDb 官方非商业数据集页面：数据可公开下载、每日刷新，但受 `personal and non-commercial use` 约束
  - https://developer.imdb.com/non-commercial-datasets/
- IMDb 官方数据字典：`name.basics.tsv.gz` 只有 `primaryName` 等基础字段；`title.akas.tsv.gz` 只覆盖 title 本地化，不覆盖人名
  - https://developer.imdb.com/non-commercial-datasets/
- Wikibase JSON 文档：实体原生包含不同语言的 `labels`、`aliases`、`sitelinks`
  - https://doc.wikimedia.org/Wikibase/master/php/docs_topics_json.html
- MediaWiki 官方文档：`wbgetentities` 可按语言取 label/alias/sitelinks，并支持 language fallback
  - https://www.mediawiki.org/wiki/API:Presenting_Wikidata_knowledge
- Wikidata `P345` 属性页：IMDb ID 适用于 `human`，且属性值稳定性标为 `never changes`
  - https://www.wikidata.org/wiki/Property:P345
- Wikidata SPARQL 服务：公开 endpoint 可直接做基于属性的查询
  - https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service
- MediaWiki 官方文档还明确指出：直接依赖 Wikipedia 页面标题有两个问题，`page titles change` 且 `it's not multilingual`
  - https://www.mediawiki.org/wiki/API:Presenting_Wikidata_knowledge

### Recommended order

按“只需要演员中文名”这个目标排序：

1. `Wikidata/Wikipedia`
   - 推荐，但具体应实现为 `Wikidata 主 + Wikipedia 辅`
2. `IMDb`
   - 不推荐作为中文名来源，只推荐作为稳定 ID 骨架
3. `Trakt`
   - 不推荐接入

### Recommended implementation stance

如果你真的要在这些公共来源里选一个进入当前 helper-only enrichment seam，我建议：

- 只研究/接 `Wikidata`
- `Wikipedia` 仅通过 `sitelinks` 做链接或中文页存在性辅助，不单独做主查询面
- `IMDb` 只在未来需要更稳 person 对齐时作为锚点使用
- `Trakt` 直接放弃

一句话版：

- `Wikidata` 是唯一“既公开可用、又真能给中文演员名”的候选
- `IMDb` 只能解决“是谁”，不能解决“中文叫什么”
- `Trakt` 连“中文叫什么”都不试图解决

## Caveats / Not Found

- 当前 session 没有 active-task 指针；本次按你明确指定的 task 目录写入研究文件。
- 我没有找到 Trakt 官方 person contract 里的多语言姓名字段；结论基于其当前公开 schema 中只存在单个 `name` 字段这一事实。
- 我没有找到 IMDb 官方公开人物数据中的中文别名契约；现有官方公开非商业数据只暴露 `primaryName`。
- `Wikidata` 虽然最可行，但它并不保证所有演员都有完整中文 label；MediaWiki 官方文档也明确提醒，不是所有属性值都翻译到了所有语言。
- 对 `Wikipedia` 的评价是“不能单独做主源”，不是“没价值”；它的价值主要来自 `Wikidata sitelinks` 后的展示/兜底，而不是独立匹配。
