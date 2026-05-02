# Research: MoviePilot PT interaction reference

- Query: 参考官方 MoviePilot 项目的 PT/媒体识别交互，提炼可执行的 PT 交互经验，并对照当前 `search_request_context/search_media/search_reply_formatter/telegram_reply_formatter` 给出下一步实现切片。
- Scope: mixed
- Date: 2026-05-01

## Findings

### Files found

- Official: `MoviePilot/app/chain/media.py`
  - 媒体识别与“搜索媒体信息”入口；把用户输入先解析成媒体候选，而不是直接进资源站搜索。
- Official: `MoviePilot/app/chain/search.py`
  - 资源搜索链；明确区分 `search_by_title()` 的模糊站点搜索与 `search_by_id()` 的精确媒体搜索。
- Official: `MoviePilot/app/agent/tools/impl/search_media.py`
  - 官方 agent 工具定义；说明“先搜媒体，再拿媒体字段”的标准输出面。
- Official: `MoviePilot/app/agent/tools/impl/search_torrents.py`
  - 官方 agent 工具定义；说明 PT 搜索需要依赖 `tmdb_id/douban_id`，即已确认媒体身份。
- Official: `MoviePilot/app/agent/tools/impl/get_search_results.py`
  - 官方 agent 工具定义；说明资源结果的站点/分辨率/促销等筛选是后续阶段，不是第一轮身份确认阶段。
- Official docs: `https://mattoid.top/docs/moviepilot/search`
  - 官方搜索文档；明确写出“先搜索媒体信息，再点卡片搜索精确资源”。
- Current repo: `app/services/search_request_context.py`
  - 当前第一轮请求上下文构造；决定何时先停在 TMDB 候选，何时直接搜 BT。
- Current repo: `app/services/search_media.py`
  - 当前 PT 主交互链；候选确认、资源搜索、缓存与二段式选择都在这里。
- Current repo: `app/services/search_reply_formatter.py`
  - 当前第一轮候选卡片与第二轮资源列表文本格式。
- Current repo: `app/bot/telegram_reply_formatter.py`
  - Telegram 渠道的候选确认排版和继续提示。

### Code patterns

- MoviePilot 把“媒体信息搜索”和“资源搜索”明确拆开：
  - `MoviePilot/app/chain/media.py:546-578`：`MediaChain.search()` 先把用户输入解析为 `MetaInfo`，再走 `search_medias(meta=meta)` 返回相关媒体列表。
  - `MoviePilot/app/chain/search.py:324-354`：`SearchChain.search_by_id()` 先 `recognize_media()`，拿到媒体身份后才 `process()` 精确搜资源。
  - `MoviePilot/app/chain/search.py:356-380`：`SearchChain.search_by_title()` 是另一条独立路径，直接返回站点资源，不做识别不过滤。
- MoviePilot 官方文档把这套分阶段交互写得很直白：
  - `https://mattoid.top/docs/moviepilot/search` lines 24-42：先“搜索媒体信息”，再通过卡片上的搜索动作进入“精确搜索”；“站点资源”则是单独的模糊搜索入口。
- MoviePilot 官方工具契约也沿用同一思路：
  - `MoviePilot/app/agent/tools/impl/search_media.py:494-623`：`search_media` 先返回媒体字段，且“精简字段，只保留关键信息”，包含 `title/en_title/year/type/season/overview/poster_path/detail_link` 等。
  - `MoviePilot/app/agent/tools/impl/search_torrents.py:517-632`：`search_torrents` 明确要求 `tmdb_id` 或 `douban_id`，并注明这些 ID 来自 `search_media`。
  - `MoviePilot/app/agent/tools/impl/get_search_results.py:579-742`：资源阶段才出现 `site/season/free_state/video_code/edition/resolution/release_group/title_pattern` 这类筛选条件。
- 我们当前代码已经具备“二段式骨架”，但触发条件和阶段边界还不够硬：
  - `app/services/search_request_context.py:39-58`：只要 `lookup_media_candidates_func()` 有结果且用户没填年份，就直接返回 TMDB 候选并停止 BT 搜索。
  - `app/services/search_media.py:303-333`：当前已能返回候选作品确认列表。
  - `app/services/search_media.py:393-470`：用户选中候选后，再按 `media_identity` 重新构造资源搜索词并搜索资源。
  - `app/services/search_media.py:502-512`：当前“是否进入候选确认”的规则几乎只看“有没有年份”，不是看媒体身份置信度或歧义程度。
  - `app/services/search_media.py:335-385`：一旦没走候选确认，第一轮仍会直接返回资源结果。
  - `app/services/search_reply_formatter.py:77-99`：第一轮候选卡片已包含 `标题/年份/类型/海报/原名/简介`。
  - `app/bot/telegram_reply_formatter.py:390-427`：Telegram 已经有单独的“候选作品”展示与“回复序号确认”的交互文案。

### 1. 第一次用户只发片名时，MoviePilot 的成熟交互原则是什么

- 结论：默认应该先做“媒体身份确认”，而不是直接做 PT 资源搜索。
- 证据：
  - 官方文档先写“搜索媒体信息”，再写“精确搜索”；精确搜索要在媒体卡片上点搜索，且“精确搜索前需要先识别媒体信息”。
  - 官方代码里 `MediaChain.search()` 和 `SearchChain.search_by_id()` 是两条不同职责的链，精确搜资源依赖已识别媒体。
- 可执行含义：
  - 标题输入的第一轮输出，应是“这是不是你要的作品”的媒体候选。
  - 资源站字段、筛选条件、做种质量等不应该在第一轮抢占主视图。

### 2. 媒体识别和资源搜索是如何分阶段的

- Stage A: 媒体识别 / 媒体搜索
  - 输入：用户自然语言标题。
  - 输出：媒体候选集合，核心是身份字段，不是资源字段。
- Stage B: 精确资源搜索
  - 输入：被确认的媒体 ID / 媒体身份。
  - 输出：与该媒体精确匹配的资源候选。
- Stage C: 资源结果再筛选
  - 输入：缓存后的资源结果。
  - 输出：按站点、季、促销状态、编码、分辨率、发布组、标题正则等继续收窄。
- 这说明：
  - “媒体识别”是第一层问题。
  - “资源相关性/筛选”是第二层问题。
  - 不应把两层问题塞进第一轮回复。

### 3. 强指向标题与模糊词该怎么处理

- 官方明确证据：两者都应先走媒体搜索/识别层，而不是直接站点 PT 搜索。
- 需要注明的推断：
  - 官方源码/文档没有把“《你的名字》必须自动选 top1、‘丧尸’必须返回 3-5 条”写成硬规则。
  - 但从其分阶段设计可以稳定推导出：
    - 强指向标题：
      - 可以突出 1 个主候选，并保留少量备选。
      - 即使主候选很强，也不应在第一轮直接下沉为 PT 资源列表；正确动作仍是“基于该媒体身份进入精确搜索”。
    - 模糊词：
      - 必须停留在媒体候选阶段，让用户先确认“到底是哪一部/哪一季/哪个系列”。
      - 不能把模糊词直接打到资源站，返回一堆标题扩展资源名让用户自己猜。

### 4. 候选卡片里哪些字段最关键，哪些不该第一轮出现

- 第一轮最关键的身份字段：
  - `title`
  - `en_title` / 原名
  - `year`
  - `type`
  - `season`（仅剧集/动漫需要）
  - `poster_path`
  - `overview`
  - `detail_link`（可选，作为深入查看入口）
- 第一轮可保留但不必强展示：
  - `vote_average`
  - `tmdb_id/imdb_id/douban_id`
- 第一轮不该出现的字段：
  - 站点名
  - 做种数
  - 体积
  - 清晰度
  - free/2xfree
  - video codec / edition / release group
  - 任何磁力、下载动作或资源站筛选器
- 原因：
  - 这些都是 Stage B / C 的资源决策字段，不是 Stage A 的作品身份字段。

### 5. 哪些做法我们当前已经接近，哪些仍偏离

- 已接近
  - 已有明确的“候选作品 -> 选序号 -> 再搜资源”二段式骨架。
  - 第一轮候选卡片字段已经接近 MoviePilot 的身份字段面。
  - Telegram 已有独立的候选确认展示与继续提示，不必重做整个渠道交互。
- 仍偏离
  - 当前是否进入候选确认，几乎由“用户有没有写年份”决定，而不是由“标题是否强指向/是否已高置信命中/是否明显模糊”决定。
  - 第一轮仍存在“没进候选确认就直接返回资源列表”的路径，这与 MoviePilot 的 media-first 原则冲突。
  - 当前还没有把“强指向标题”和“模糊词”拆成不同的候选输出策略。
  - 第一轮虽然已显示身份字段，但第二轮资源搜索的触发边界还不够硬，仍可能被预先猜中的 TMDB 标题扩展牵着走。

### 下一步实现切片（按优先级）

1. `P0`：把“是否停在媒体候选确认”从“缺少年份判断”改成“媒体身份置信度判断”。
   - 目标文件：`app/services/search_request_context.py`, `app/services/search_media.py`
   - 要点：引入至少三态 `high_confidence / ambiguous / empty`；`_should_confirm_media_candidates()` 不再只看 `year`。

2. `P1`：硬化阶段边界，只要拿到可用媒体候选，第一轮就不返回 PT 资源列表。
   - 目标文件：`app/services/search_media.py`
   - 要点：把 `search_and_format()` 的第一轮输出固定为“媒体候选确认”；资源搜索只允许从 `search_resources_for_selected_media()` 进入。

3. `P2`：为强指向标题与模糊词建立不同的候选收敛策略。
   - 目标文件：`app/services/search_request_context.py`
   - 要点：强指向标题输出 `1 个主候选 + 1-2 个兜底`；模糊词输出 `3-5 个最相关候选`；排序应综合本地化标题/原名精确匹配、年份、媒体类型。

4. `P3`：收紧第一轮候选卡片字段，只保留“判断作品身份”必需项。
   - 目标文件：`app/services/search_reply_formatter.py`, `app/bot/telegram_reply_formatter.py`
   - 要点：保留 `海报/标题/原名/年份/类型/简介`，隐藏所有资源站与内部 ID 字段；继续保留数字确认。

5. `P4`：把“选中后的 media_identity”变成唯一资源搜索入口，不再让预判 TMDB 结果提前影响第一轮体验。
   - 目标文件：`app/services/search_request_context.py`, `app/services/search_media.py`
   - 要点：第一轮只做 identity；第二轮再用已确认的 `media_identity` 生成资源查询词。

### External references

- GitHub repo: https://github.com/jxxghp/MoviePilot
- Official search docs: https://mattoid.top/docs/moviepilot/search
- Official code:
  - https://github.com/jxxghp/MoviePilot/blob/v2/app/chain/media.py
  - https://github.com/jxxghp/MoviePilot/blob/v2/app/chain/search.py
  - https://github.com/jxxghp/MoviePilot/blob/v2/app/agent/tools/impl/search_media.py
  - https://github.com/jxxghp/MoviePilot/blob/v2/app/agent/tools/impl/search_torrents.py
  - https://github.com/jxxghp/MoviePilot/blob/v2/app/agent/tools/impl/get_search_results.py
  - https://github.com/jxxghp/MoviePilot/blob/v2/app/agent/tools/impl/recognize_media.py

### Related specs

- `.trellis/spec/backend/index.md`
- `.trellis/spec/backend/bt-source-contracts.md`
- `.trellis/spec/backend/quality-guidelines.md`
- `.trellis/tasks/05-01-pt-relevance-adult-bt-sources/prd.md`

## Caveats / Not Found

- `python3 ./.trellis/scripts/task.py current --source` 当前返回 `Current task: (none)`；本次研究是按你明确指定的 task 目录写入，而不是按 Trellis 当前指针自动解析。
- 官方文档没有把“强指向标题自动 top1、模糊词固定返回 3-5 条”写成显式产品规则；这部分属于基于官方 staged architecture 的推断，不是逐字文档声明。
- 没有找到独立于 GitHub repo / `mattoid.top` 之外、可稳定访问的官方 wiki 页面；本次主要依据官方 repo 与官方 docs。
- 本次未研究 MoviePilot 的具体 Telegram / IM 渠道 UI 文案实现；结论基于官方搜索文档、核心 `chain` 代码和官方 agent tool 契约。
