# Research: moviepilot-douban-api-feasibility

- Query: 基于既有 `moviepilot-douban-core-trace.md`，评估 MoviePilot core 的 Douban API / Frodo 路线能否复用到 Luminarr 当前的 `TMDB-first + domestic helper-only` 后处理链里；明确可借用点、不可照搬点，以及最值得做的 feasibility 实验
- Scope: mixed
- Date: 2026-05-04

## Findings

### Direct answer

结论不是“整条 Frodo 路线可以直接搬过来”，而是：

- **可部分复用**：MoviePilot 的 `IMDb -> Douban subject -> celebrities -> localized cast merge` 这套匹配与 merge 思路，技术上可以挂到我们现有 `DomesticCastEnrichmentService` 后面。
- **不应直接复用**：MoviePilot 里依赖的 Frodo 私有 API、签名、硬编码 key/secret、随机 Android UA，不适合作为我们正式产品链的默认实现。
- **最稳落点**：继续保持 `TMDB` 为唯一 identity / thumb 主源，只把国内源当成 `演员中文名 / 角色中文名` 的 helper-only enrich；如果要进一步试 Frodo，也只能先做隔离实验，不进入主链。

### Files found

- `.trellis/tasks/05-04-moviepilot-post-processing-quality-upgrade/research/moviepilot-douban-core-trace.md`
  - 已追出 MoviePilot core 里 `match_doubaninfo()` / `douban_info()` 的真实调用链、Frodo endpoints、签名与 IMDb 反查路径
- `.trellis/tasks/05-04-moviepilot-post-processing-quality-upgrade/research/domestic-enrichment-sources.md`
  - 已确定当前 task 的推荐边界是 `TMDB-first + Douban helper-only`
- `app/services/metadata_scraper.py`
  - 我们当前 metadata 链已预留国内 cast enrichment seam，且 merge / fail-soft / NFO 输出边界都已存在
- `app/services/domestic_cast_enrichment.py`
  - helper-only contract 已抽象成独立 service，不要求具体来源必须是 HTML 或 API
- `app/clients/douban_cast_helper.py`
  - 当前 Douban helper 走的是 `subject_suggest + subject HTML`，不是 Frodo；这正好提供了“现状 vs MoviePilot”对照
- `app/clients/tmdb.py`
  - 当前已有 TMDB detail / credits，但没有 IMDb `external_ids` 锚点能力
- `tests/test_metadata_scraper.py`
  - 已验证国内 helper 只能覆盖 `name` / `character`，且国内头像 URL 不进入 NFO 主 `<thumb>`
- `tests/test_douban_cast_helper.py`
  - 已验证当前 helper 的 browser-like header、query fallback 与 HTML cast 解析行为
- `.trellis/spec/backend/bt-source-contracts.md`
  - 已定义 helper-only enrichment、主源/辅源分离、软失败等项目边界

### Key route elements required by the MoviePilot Frodo path

1. **Frodo / Douban API surface**
   - `https://frodo.douban.com/api/v2`
   - 搜索入口：`/search/weixin`
   - subject detail：`/movie/<id>` / `/tv/<id>`
   - cast detail：`/movie/<id>/celebrities` / `/tv/<id>/celebrities`
   - IMDb 反查：`POST https://api.douban.com/v2/movie/imdb/<imdbid>`
2. **签名与凭据**
   - MoviePilot core 在 `app/modules/douban/apiv2.py` 中内置 `_api_key` / `_api_secret_key`
   - 请求路径需要 HMAC-SHA1 `_sig`
   - 同时配合随机 Android UA、`requests.Session`、缓存
3. **匹配锚点**
   - 有 `imdbid` 时优先 IMDb 反查 subject
   - 没有 `imdbid` 才回退到 `name + year (+ season)` 搜索匹配
4. **消费字段**
   - `localized actor name`
   - `localized character`
   - `avatar.large` 这类人物头像字段
5. **运行前提**
   - 只有 rate-limit 检测，没有 challenge/captcha/browser fallback
   - 默认假设 Douban 私有接口可持续访问

### What we can borrow

#### 1. 借“匹配策略”，不是先借 transport

MoviePilot 最有价值的不是 Frodo URL 本身，而是它把 **IMDb 当强锚点**：

- 上游 trace 显示 `match_doubaninfo()` 优先走 `imdbid(imdbid)`，只有没有 IMDb 时才回退 `search(f"{name} {year}")`
  - `MoviePilot/app/modules/douban/__init__.py:623-670`
  - `MoviePilot/app/modules/douban/apiv2.py:221-248`
- 这点正好能补我们当前 helper 的短板：我们现在只用标题/原名 + 年份匹配 Douban subject
  - `app/clients/douban_cast_helper.py:50-62`
  - `app/clients/douban_cast_helper.py:119-142`

对 Luminarr 来说，**最值得借的第一步**是把 IMDb 锚点补到我们自己的 helper 入口，而不是先把 Frodo transport 搬进来。

#### 2. 借“后置 enrich seam”

我们当前 metadata 链已经是很适合挂这类 helper 的结构：

- 先拿 TMDB detail + credits
- 先构建 TMDB `cast_truth`
- 再调用 `DomesticCastEnrichmentService`
- 再把 enrich 后的 cast 写入 metadata / NFO

代码边界已经在：

- `app/services/metadata_scraper.py:142-154`
- `app/services/metadata_scraper.py:283-337`
- `app/services/domestic_cast_enrichment.py:9-46`

这意味着如果未来要试一个 `FrodoCastHelperClient`，它完全可以只替换 lookup 实现，而不需要改 metadata 输出契约。

#### 3. 借“字段级 merge 规则”

我们现在的 merge 规则已经和推荐方向一致：

- 国内 helper 只覆盖 `name` / `character`
- 国内头像只额外写 `domestic_profile_image_url`
- NFO `<thumb>` 仍然只用 `profile_image_url`（即 TMDB）

证据：

- `app/services/metadata_scraper.py:326-335`
- `app/services/metadata_scraper.py:230-245`
- `tests/test_metadata_scraper.py:549-598`

所以如果 Frodo `celebrities` 能稳定给出中文演员名/角色名，**它的数据模型可以直接映射到现有 `DomesticCastMatch`**，不需要改 output schema。

#### 4. 借“软失败和 helper-only”运行方式

这类国内源接入必须是 best-effort：

- helper 报错时直接回退 TMDB-only cast truth
  - `app/services/metadata_scraper.py:298-306`
- 现有 spec 也明确要求 provider/helper split、静态请求、软失败、不提升为主源
  - `.trellis/spec/backend/bt-source-contracts.md:146-152`
  - `.trellis/spec/backend/bt-source-contracts.md:199-202`

这和 MoviePilot 实际把 Douban 放在补充链位置的用法是兼容的。

### What we should not copy directly

#### 1. 不能照搬私有 key / secret / 签名实现

这是最大红线。

- 上游 trace 已确认 MoviePilot Frodo client 依赖内置 `_api_key` / `_api_secret_key` 和 HMAC-SHA1 `_sig`
  - `MoviePilot/app/modules/douban/apiv2.py:152-204`
- 这类凭据和签名逻辑如果直接搬进来，本质上是在复制一个 **未授权、不可审计、不可持续** 的私有接入方式。

即便纯技术上能跑，也不适合进入我们默认主线。

#### 2. 不能把未公开契约的私有 API 当正式依赖

当前我们自己的 Douban helper 虽然更“原始”，但它至少是显式的 HTML best-effort 路线：

- `j/subject_suggest` + `subject/<id>/?dt_dapp=1`
  - `app/clients/douban_cast_helper.py:53-59`
  - `tests/test_douban_cast_helper.py:58-66`

而 Frodo 这条线的问题是：

- API schema 不公开
- key/secret 不公开
- 没有官方 SLA
- 没有 challenge/captcha/browser fallback
- 一旦 Douban 改签名或封 transport，主链就断

所以它可以做 **隔离实验**，不适合做 **正式产品依赖**。

#### 3. 不能让国内源改写 identity truth

我们当前链路的 identity truth 仍应来自 TMDB，而不是 Douban：

- 先按 TMDB 构建 `cast_truth`
  - `app/services/metadata_scraper.py:142-154`
- 再做 localized overwrite
  - `app/services/metadata_scraper.py:317-336`
- 当前 `TmdbClient` 的公开能力也清晰围绕 TMDB detail / credits，而不是双主源
  - `app/clients/tmdb.py:75-176`
  - `app/clients/tmdb.py:229-329`

因此即便 Frodo 路线能用，也只能改：

- `name`
- `character`
- 可选 `domestic_profile_image_url`

不能改：

- `id`
- `original_name`
- `original_character`
- `order`
- `profile_image_url`

#### 4. 不能把 Douban 头像变成第一阶段成品链主图

MoviePilot 插件消费过 `avatar.large` 一类字段，这在我们这里最多只能作为候选 truth：

- 当前测试明确要求国内头像 URL 不进入 NFO `<thumb>`
  - `tests/test_metadata_scraper.py:590-598`

这和 task PRD 里“头像继续 TMDB-first、国内头像最多低信任候选”的方向一致。

### Feasibility judgment for Luminarr

#### Technically feasible

**可行的部分**是：

- 在 `DomesticCastEnrichmentService` 背后新增另一种 lookup 实现
- 继续输出现有 `DomesticCastMatch`
- 用 TMDB cast 作为基座，只做字段级 localized merge

也就是说，**从软件结构上讲，这条路线是“可插拔”的**。

#### Productization not recommended

**不建议正式接入的部分**是：

- 直接把 MoviePilot 的 Frodo transport 当默认来源
- 把私有 key/secret/signature 带入仓库
- 把 Douban 私有 API 当稳定依赖

所以更准确的结论应是：

- **架构层面：可以借**
- **实现层面：只建议借思路和接口边界**
- **transport 层面：不建议直接照搬**

### Best 1-2 feasibility experiments

#### Experiment 1: IMDb anchor experiment (highest value)

目标：验证“真正提升我们匹配精度的，到底是不是 Frodo transport，还是 IMDb 锚点本身”。

建议做法：

1. 先给 `TmdbClient` 增加 `external_ids` / `imdb_id` 能力
   - 当前代码里未见 `external_ids` / `imdb_id` 查询接口
   - `app/clients/tmdb.py:75-176`
2. 基于 5-10 个已确认样本，做一个对照：
   - A 组：现有 `subject_suggest + title/year`
   - B 组：IMDb 先校验，再落 subject
3. 只看：
   - subject 匹配命中是否更稳
   - cast 对齐是否更少歧义
   - 是否不需要改 metadata merge contract

为什么它最值：

- 不需要私有 Frodo 凭据
- 可以直接回答“是 transport 带来的收益，还是 IMDb anchor 带来的收益”
- 即便最终放弃 Frodo，这个实验的产出仍可复用

#### Experiment 2: Isolated Frodo transport probe (only as a sandbox)

目标：回答“如果只从纯技术角度看，MoviePilot 那套 Frodo 签名今天还跑不跑得通”。

建议做法：

1. 不接入主链
2. 单独做一个隔离 probe
3. 只测 1-2 个样本：
   - `imdb -> subject`
   - `subject -> celebrities`
4. 记录：
   - 请求是否成功
   - 返回 payload 是否含我们需要的 `localized_name / localized_character / avatar`
   - 是否立刻遇到 403 / rate limit / schema drift

终止条件也要明确：

- 没有合法、可配置的凭据来源 -> 停
- Frodo schema / 签名不稳定 -> 停
- 只能靠仓库内置私有 secret 才能通 -> 停

这个实验的价值不是“证明应该接入”，而是尽快证明 **不值得接入** 或 **只适合做临时研究工具**。

### Code patterns

- MoviePilot Frodo 路线优先用 IMDb 反查，再退 title/year 搜索：
  - `MoviePilot/app/modules/douban/__init__.py:623-670`
  - `MoviePilot/app/modules/douban/apiv2.py:221-248`
- MoviePilot Douban detail / celebrities 通过 Frodo API 获取，不是 HTML 抓取：
  - `MoviePilot/app/modules/douban/__init__.py:425-470`
  - `MoviePilot/app/modules/douban/apiv2.py:354-376`
- MoviePilot Frodo transport 依赖 API key / secret / `_sig` 签名 / Android UA / session / cache：
  - `MoviePilot/app/modules/douban/apiv2.py:152-204`
- 我们当前 helper 走的是 `subject_suggest + subject HTML`：
  - `app/clients/douban_cast_helper.py:50-62`
  - `app/clients/douban_cast_helper.py:102-107`
  - `app/clients/douban_cast_helper.py:145-177`
- 我们现有 metadata 链已经把国内 helper 放在 TMDB cast_truth 之后：
  - `app/services/metadata_scraper.py:142-154`
  - `app/services/metadata_scraper.py:283-337`
- 当前 merge contract 只允许国内 helper 覆盖 localized text，保留 TMDB thumb：
  - `app/services/metadata_scraper.py:326-335`
  - `app/services/metadata_scraper.py:230-245`
  - `tests/test_metadata_scraper.py:579-598`
- 当前 helper 的 browser-like header 与 fallback 行为已被测试钉住：
  - `tests/test_douban_cast_helper.py:11-66`
  - `tests/test_douban_cast_helper.py:69-122`
- helper-only / provider split / fail-soft 是项目既有 contract，不是临时建议：
  - `.trellis/spec/backend/bt-source-contracts.md:146-152`
  - `.trellis/spec/backend/bt-source-contracts.md:173-181`
  - `.trellis/spec/backend/bt-source-contracts.md:199-202`

### External references

- MoviePilot upstream repository
  - https://github.com/jxxghp/MoviePilot
- TMDB official External IDs docs
  - https://developer.themoviedb.org/reference/movie-external-ids
  - 用途：如果要借 MoviePilot 的 IMDb-first 思路，我们应优先从 TMDB 官方接口拿 IMDb，而不是先引 Frodo
- Douban legal statement
  - https://www.douban.com/about/legal
  - 2026-05-04 查阅；页面明确把 API 接入、数据抓取、衍生利用都纳入使用限制/授权边界

### Related specs

- `.trellis/spec/backend/bt-source-contracts.md`
  - helper-only enrichment / provider-helper split / fail-soft 的通用约束
- `.trellis/tasks/05-04-moviepilot-post-processing-quality-upgrade/prd.md`
  - 当前 task 已明确锁定 `TMDB` 为唯一主源、国内源仅做 helper-only enrich
- `.trellis/tasks/05-04-moviepilot-post-processing-quality-upgrade/research/moviepilot-douban-core-trace.md`
  - 本文件的 upstream Frodo 细节来源
- `.trellis/tasks/05-04-moviepilot-post-processing-quality-upgrade/research/domestic-enrichment-sources.md`
  - 本文件的产品边界前提来源

## Caveats / Not Found

- 当前 Trellis active-task 指针为空；本次按用户明确指定的 task 目录写入研究产物，而不是依赖 `task.py current`。
- 本次没有发真实 Douban / Frodo 线上请求；对签名是否仍有效、当前 rate-limit/403 频率、payload 是否漂移的判断，不是 live verification。
- 没有发现我们现有 `TmdbClient` 暴露 `external_ids` / `imdb_id` 能力；如果要复用 MoviePilot 的 IMDb-first 思路，第一步应先补这个锚点。
- 没有找到 Douban 面向第三方正式开放、可授权复用、覆盖 Frodo 同等级字段的电影 API 文档；因此本结论默认把 Frodo 视为私有/非正式接口。
