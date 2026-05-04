# Research: moviepilot-douban-core-trace

- Query: 追踪 MoviePilot `plugins.v2/personmeta/__init__.py` 对 `match_doubaninfo()` 与 `douban_info()` 的依赖链，确认豆瓣 subject / 演员数据如何获取，以及是否存在反爬挑战页、验证码或浏览器化处理
- Scope: mixed
- Date: 2026-05-04

## Findings

### Direct answer

- `personmeta` 插件并不是直接 import `DoubanChain`；它通过插件基类注入的 `self.chain = PluginChian()` 走 `ChainBase` 动态分发，因此插件依赖的是 MoviePilot core 暴露出来的“豆瓣处理链能力”，不是某个单独 client。
- `self.chain.match_doubaninfo()` / `self.chain.douban_info()` 的链路入口在 `MoviePilot/app/chain/__init__.py:170-183`，真正的方法体在 `MoviePilot/app/modules/douban/__init__.py:151-470` 与 `MoviePilot/app/modules/douban/__init__.py:611-671`。
- 这两条链路不是网页 HTML 抓取，也不是浏览器自动化；本质上是 `DoubanApi` 对豆瓣私有/移动端 API 的仓库内薄封装：`frodo.douban.com/api/v2` + `api.douban.com/v2/movie/imdb/<imdbid>`。
- 代码里能看到的“抗风控”只有签名、随机 Android UA、`requests.Session`、缓存、速率限制检测、插件侧随机 sleep；没有发现 challenge 页绕过、验证码识别、Playwright/Selenium/browser 化兜底。

### Files found

- `MoviePilot-Plugins/plugins.v2/personmeta/__init__.py`
  - 插件侧演员补全逻辑；`__get_douban_actors()` 直接调用 `self.chain.match_doubaninfo()` 和 `self.chain.douban_info()`
- `MoviePilot/app/plugins/__init__.py`
  - `_PluginBase` 注入 `self.chain = PluginChian()`
- `MoviePilot/app/chain/__init__.py`
  - `ChainBase.run_module()` / `ChainBase.match_doubaninfo()` 的动态模块分发入口
- `MoviePilot/app/modules/douban/__init__.py`
  - `DoubanModule` 对 `match_doubaninfo()` / `douban_info()` 的具体实现
- `MoviePilot/app/modules/douban/apiv2.py`
  - 豆瓣请求 client；定义 endpoints、签名、UA、session、缓存
- `MoviePilot/app/utils/http.py`
  - 纯 `requests` 包装；可用于判断是否存在浏览器化处理

### Code patterns

- 插件调用链：
  - `MoviePilot-Plugins/plugins.v2/personmeta/__init__.py:693-710`
  - 先随机休眠 `3-10` 秒，再调用 `self.chain.match_doubaninfo(...)`，匹配到 subject 后再调用 `self.chain.douban_info(id)`，最后把 `actors + directors` 返回给人物补全逻辑
- 插件如何消费豆瓣演员字段：
  - `MoviePilot-Plugins/plugins.v2/personmeta/__init__.py:624-661`
  - 使用 `name`、`title`、`character`、`avatar.large`、`latin_name` 来更新演员中文名、简介、角色名和头像；图片优先 TMDB，缺失时才 fallback 到豆瓣头像
- 插件链路注入与分发：
  - `MoviePilot/app/plugins/__init__.py:38-43`
  - `_PluginBase.__init__()` 把 `self.chain` 设为 `PluginChian()`
  - `MoviePilot/app/chain/__init__.py:78-138`
  - `run_module()` 会查找所有实现了对应方法的 running module，并按顺序执行
  - `MoviePilot/app/chain/__init__.py:170-183`
  - `match_doubaninfo()` 只是 wrapper，本身不做匹配逻辑
- `match_doubaninfo()` 的真实逻辑：
  - `MoviePilot/app/modules/douban/__init__.py:623-633`
  - 如果有 `imdbid`，优先调用 `self.doubanapi.imdbid(imdbid)`，直接返回豆瓣 subject
  - `MoviePilot/app/modules/douban/__init__.py:635-670`
  - 否则调用 `self.doubanapi.search(f"{name} {year}")`；然后筛掉非 `movie/tv` 项，按 `mtype`、`year`、`season` 和 `MetaInfo(title).name == name` 做精确匹配
- `douban_info()` 的真实逻辑：
  - `MoviePilot/app/modules/douban/__init__.py:425-470`
  - 电影走 `movie_detail(id)` + `movie_celebrities(id)`，剧集走 `tv_detail(id)` + `tv_celebrities(id)`，把 `directors` / `actors` 直接 merge 进 detail dict
  - `MoviePilot/app/modules/douban/__init__.py:431-455`
  - 只做 `subject_ip_rate_limit` 检测并可抛 `APIRateLimitException`，没有更深的 challenge/captcha 处理
- Douban API transport 的实现方式：
  - `MoviePilot/app/modules/douban/apiv2.py:152-204`
  - `_base_url = "https://frodo.douban.com/api/v2"`，内置 `_api_key` / `_api_secret_key`，对请求路径做 HMAC-SHA1 `_sig` 签名，随机 Android UA，`requests.Session` 复用，`lru_cache` 缓存
  - `MoviePilot/app/modules/douban/apiv2.py:221-240`
  - IMDb 反查走 `POST https://api.douban.com/v2/movie/imdb/<imdbid>`，带 `apikey`
  - `MoviePilot/app/modules/douban/apiv2.py:242-248`
  - 关键字搜索走 `GET /search/weixin`
  - `MoviePilot/app/modules/douban/apiv2.py:354-376`
  - subject detail 与 celebrities 分别走 `/movie/<id>`、`/movie/<id>/celebrities`、`/tv/<id>`、`/tv/<id>/celebrities`
  - `MoviePilot/app/modules/douban/apiv2.py:491-497`
  - 人物详情另有 `/elessar/subject/<person_id>`，但不在这次追踪的两条主调用链里
- 无浏览器化证据：
  - `MoviePilot/app/utils/http.py:14-175`
  - `RequestUtils` 只是 `requests` / `Session` 的普通包装
  - 本次对目标链路文件检索了 `captcha`、`challenge`、`sec.douban`、`playwright`、`selenium`、`browser`，未发现对应处理

### Implementation judgment for Luminarr

#### Worth borrowing

- 先用强 identity 锚点，再做 subject 匹配：
  - IMDb ID 优先，标题/年份/季号只做 fallback
- 把国内源放在“后置 enrichment”而不是“主识别真相”：
  - 先有 canonical media identity，再去补演员中文名/角色名
- 字段级 merge 策略可借：
  - 图片 TMDB-first，中文名/角色名可 domestic helper-only
- 软失败和节流思路可借：
  - 缓存、短休眠、速率限制检测、失败不阻断主链

#### Should not copy directly

- 不应照抄硬编码的 Douban API key / secret / Frodo 签名方案
- 不应把私有移动端 API 当作生产主链硬依赖
- 不应假设 `actors/directors` payload 长期稳定
- 不应把“只有 rate-limit 检测、没有 challenge/captcha/browser 兜底”的实现当作稳健抓取方案

### External references

- Upstream repositories fetched on 2026-05-04:
  - `https://github.com/jxxghp/MoviePilot`
  - `https://github.com/jxxghp/MoviePilot-Plugins`
- No official/public Douban docs were referenced by MoviePilot for these endpoints.
- Observed endpoint families in source:
  - `https://frodo.douban.com/api/v2`
  - `https://api.douban.com/v2/movie/imdb/<imdbid>`

### Related specs

- `.trellis/spec/backend/bt-source-contracts.md`
  - 已定义 helper-only enrichment / fail-soft 的项目边界，可直接约束我们如何借 MoviePilot 的思路
- `.trellis/tasks/05-04-moviepilot-post-processing-quality-upgrade/research/domestic-enrichment-sources.md`
  - 已有结论是 `TMDB-first + 豆瓣 helper-only`，本次源码追踪验证了 MoviePilot 在人物中文化上也基本是这个结构

## Caveats / Not Found

- 当前 Trellis active-task 指针为空；本次按用户明确指定的 task 目录落研究文件。
- 本次没有执行实时 Douban 网络请求；关于速率限制、挑战页、验证码的判断基于源码静态追踪，不是线上实测。
- `DoubanApi.person_detail()` 存在，但不在 `personmeta -> __get_douban_actors() -> match_doubaninfo() / douban_info()` 这条主链里；若后续要研究人物页补全，再单独开一份 research 更合适。
