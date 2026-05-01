# PT relevance-first search and adult BT source completion

## Goal

让 PT 搜索从“年份驱动的歧义澄清”改成“相关性优先的候选确认”，并把 adult BT 从“消息样式和 metadata 壳基本完成，但资源源仍经常为空”推进到“真正能返回成人 BT 资源结果”。

## What I already know

* 当前 `SearchMediaService.search_and_format()` 会先构造 TMDB 搜索上下文，但当 TMDB 不够 confident 且结果分歧较大时，容易回到“补年份 / 歧义澄清”路径。
* 当前 PT Telegram 搜索结果已经有电影卡片和候选列表，但海报仍写死为 `海报: 暂未接入图片`，结果里也没有清楚区分 `movie / tv`。
* 当前 adult BT Telegram 结果样式、adult metadata source policy、Avmoo -> JavLibrary helper chain 已有实现。
* 当前 adult BT 真正的问题不只是样式，而是：
  * `BT_WEB_SOURCES` 当前可能为空，主动成人 BT 资源源没有配置或没有真正接通；
  * helper / metadata 来源目前只有 `Avmoo -> JavLibrary` 真正落地，用户点名的其它来源还没有落成真实 client。
* 用户这轮明确要求：
  * PT 搜索不应默认要求补年份；
  * 模糊词如 `丧尸` 也应先返回最相关候选；
  * 指向性较强的名称如 `你的名字` 应自动缩小范围并返回最相关 TMDB 信息；
  * adult BT 问题要“真正解决好”，不是只停在 metadata 壳。

## Requirements

### R1. PT 搜索改为 relevance-first

* 用户只发片名时，不默认要求补年份。
* 搜索应按用户输入内容的相关性收敛，而不是先按 `movie / tv / anime` 或年份硬分流。
* `movie / tv / anime` 都要纳入候选范围，并按相关性返回。
* 模糊词（例如 `丧尸`）要返回 3-5 个最相关候选，供用户确认“到底是哪一部 / 哪一季 / 哪个系列 / 哪部动漫作品”。
* 指向性较强的片名（例如 `你的名字`）要尽量自动缩小范围，优先返回最相关主候选，并保留少量兜底候选。
* 对 `你的名字` 这类强指向标题，相关性排序必须强偏置 exact TMDB 媒体命中，而不是被资源侧扩展标题、合集标题或相似长标题带偏。
* 对这类强指向标题，优先级应接近“媒体识别”而不是“资源搜索”；也就是说，用户首先应该看到“是不是这部作品”的确认卡片，而不是一堆资源名扩展。

### R2. PT 搜索结果要带 TMDB 基础信息

* 搜索结果要尽量展示最相关 TMDB 信息：
  * 海报
  * 中文/原始标题
  * 年份
  * 类型（movie / tv）
  * 简短辅助信息（如别名或一句简介）
* Telegram 交互继续保留数字选择，但应先让用户“看懂是哪一个”，再要求选择。
* PT 搜索必须拆成两段：
  * 先返回媒体候选确认（TMDB / media identity）
  * 用户选定具体作品后，再去搜资源
* 不能把“媒体候选信息”和“资源搜索结果”在第一轮一起返回；否则强指向标题也会被资源名扩展带偏。
* 第一轮 Telegram 回复要尽量参考 MoviePilot 的“先识别媒体，再精确搜资源”的体验，而不是直接把资源搜索结果和媒体信息混在一起。

### R3. adult BT 必须真正返回资源

* adult BT 不接受继续停在“成人源为空、只读没结果”的半完成态。
* 需要把主动 adult BT 资源源真正接通，让 `成人搜` 可以在 adult-only 边界内返回可操作的 BT 资源结果。
* 当 `BT_WEB_SOURCES` 为空时，系统要自动启用一组 curated 默认 adult BT provider，而不是完全退回“空配置即空结果”。
* 不能把 adult metadata/helper 来源和 BT 资源源混成一类实现；要分清：
  * 哪些来源负责“搜 BT 资源”
  * 哪些来源负责“补海报 / 标题 / 演员 / 详情”

### R4. 接入当前讨论过的成人信息来源

* 用户点名过的来源都要纳入当前设计与实现范围评估：
  * `avmoo`
  * `avbase`
  * `jav321`
  * `avsox`
  * `caribbeancom`
  * `missav`
  * `javlibrary`
  * `javbus`
  * `fanza`
* 但这些来源不要求全都承担同一角色；实现时要按职责划分为：
  * BT provider
  * metadata/helper
  * conditional source
* 对用户点名过的成人信息站，目标不是“只是登记 policy”，而是尽量做到“基本都能查到信息”，至少在 metadata/helper 角色上真正可用。
* adult BT 的完成标准不是只有海报卡片；还必须做到“用户肉眼能在这些 BT 网站搜到的资源，机器人也能尽量搜到”，避免继续出现“站点有资源，但机器人搜不到”的落差。
* adult BT 返回消息必须重排成高可读卡片：
  * 海报优先
  * 中文字段名优先
  * 日本站点原始字段尽量翻成中文标签
  * metadata 信息与 BT 资源信息分组展示
* adult BT 卡片不能继续表现成“信息很多但排版很烂、海报看不到、关键信息不聚合”。
* adult BT 卡片的用户目标不是“展示很多行文本”，而是“让我一眼判断这是不是我要的资源，并且能马上复制/点击磁力或继续后续动作”。

## Acceptance Criteria

* [ ] PT 搜索在只发片名时，不默认要求补年份，而是返回按相关性排序的候选。
* [ ] `丧尸` 这类模糊词会返回最相关 TMDB 候选，并附带足够信息帮助用户确认。
* [ ] `你的名字` 这类指向性较强的词会自动收窄到主候选，并附带少量兜底候选。
* [ ] `movie / tv / anime` 都会进入同一套 relevance-first 候选收敛逻辑，而不是先要求用户补类型。
* [ ] PT Telegram 搜索第一轮只展示媒体候选确认卡片，不混入资源搜索结果。
* [ ] PT Telegram 搜索结果展示海报、标题、年份、类型和基础辅助信息。
* [ ] `你的名字` 这类强指向作品在第一轮应先收敛到日本动漫电影本体，而不是返回大量扩展资源名。
* [ ] adult BT 在 adult-only 边界内能真正返回资源结果，不再只停留在 metadata/helper 壳。
* [ ] 当前讨论过的成人来源都被纳入实现方案，且角色边界清楚。
* [ ] 至少主要成人信息源在 helper / metadata 层真正可查到信息，而不是只停留在排序 policy。
* [ ] adult BT Telegram 卡片优先显示海报，并把核心字段整理成中文友好的结构化排版。

## Out of Scope

* 不重做整条多渠道搜索架构。
* 不把 PT 搜索改成强依赖某一个外部产品的完全复制品。
* 不放宽 adult-only、显式 confirm、watchlist sync fail-closed 这些既有边界。
* 不把所有成人来源都强行做成 BT 主动搜索 provider。

## Open Questions

* 无用户侧未决问题。当前剩余判断属于实现层设计决策：
  * 哪些点名来源应归为 BT provider，哪些应归为 metadata/helper；
  * PT 搜索对“模糊但相关”的返回阈值如何定义。

## Technical Notes

* 当前相关入口：
  * `app/services/search_request_context.py`
  * `app/services/search_media.py`
  * `app/services/search_reply_formatter.py`
  * `app/bot/telegram_reply_formatter.py`
  * `app/services/adult_metadata_sources.py`
  * `app/clients/adult_read_only_helper_chain.py`
  * `app/main.py`
