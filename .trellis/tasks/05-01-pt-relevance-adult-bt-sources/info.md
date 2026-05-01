# Autoplan Review — PT relevance-first search and adult BT source completion

## Review Status

- Branch: `main`
- Review mode: `SELECTIVE_EXPANSION`
- UI scope: `yes`
- DX scope: `no`
- Outside voice: attempted via `codex exec`; output was context-heavy and not cleanly structured, so this review keeps it as a supporting signal, not a primary gate.

## Phase 1 — CEO Review

### Premise challenge

Accepted premises:

1. PT 搜索不该默认把用户赶回“补年份”，而应该先给最相关候选。
2. `movie / tv / anime` 不应先被硬分流；它们应该都进入同一套相关性收敛逻辑。
3. adult BT 的用户价值不是“有 metadata 卡片”，而是“机器人能尽量搜到人类肉眼可搜到的资源，并附带可信信息卡片”。

### Existing code leverage map

| Sub-problem | Existing leverage |
|---|---|
| PT 搜索请求归一化 | `app/services/search_request_context.py` |
| PT 搜索排序与候选缓存 | `app/services/search_media.py` |
| 搜索结果卡片与 Telegram 文本变换 | `app/services/search_reply_formatter.py`, `app/bot/telegram_reply_formatter.py` |
| TMDB 查询 | `app/clients/tmdb.py` |
| adult BT provider role registry | `app/services/bt_sources.py` |
| adult metadata/helper role registry | `app/services/adult_metadata_sources.py` |
| adult helper chain | `app/clients/adult_read_only_helper_chain.py` |

### Dream state

```text
CURRENT
  PT 搜索：模糊词容易回“补年份”
  adult BT：消息壳和部分 metadata 已有，但资源源常空

THIS PLAN
  PT 搜索：相关性优先候选 + TMDB 卡片 + 数字确认
  adult BT：BT provider 真接通 + metadata/helper 多源补全

12-MONTH IDEAL
  一个统一的 media intent 搜索面
  任何片名都先回最相关候选
  adult BT 同时具备可搜资源、可信 metadata、去重/确认/状态闭环
```

### Alternatives considered

| Approach | Pros | Cons | Verdict |
|---|---|---|---|
| A. 只改 PT 相关性，不动 adult BT | 风险低，改动小 | 留下半完成 adult BT 主线 | Reject |
| B. PT relevance-first + adult BT provider/helper 分层 | 同时解决两个用户痛点，边界清楚 | 范围较大，需要强约束 | Accept |
| C. 直接重做统一跨渠道搜索平台 | 长期最整齐 | 过重，和当前 blast radius 不符 | Reject |

### CEO findings

1. `High`：当前 PRD 必须明确“anime 不是第三套搜索后端”，而是 `movie / tv` 候选里的相关性问题。否则实现很容易做成三套分支逻辑。
   - Fix: 统一 media candidate pipeline，类型作为候选属性而不是入口分支。
2. `High`：adult BT 不能承诺“所有点名网站都做 BT 搜索 provider”。
   - Fix: 明确 `BT provider` 与 `metadata/helper` 的角色边界，避免把站点能力和用户期望混淆。
3. `Medium`：当前用户口中的“像 MoviePilot 那样”本质上是在要“先给最相关候选，再确认”，而不是要复制某个产品的完整信息架构。
   - Fix: 对标交互原则，不复制产品表面。

### Error & Rescue Registry

| Risk | What user sees | Rescue |
|---|---|---|
| 模糊词返回大量噪声候选 | 用户仍然不知道该选哪一个 | 引入 relevance ranking + 限定 3-5 个候选 |
| TMDB 命中弱但 Prowlarr 有结果 | 结果卡片信息薄弱或错位 | 允许 low-confidence TMDB candidates 进入候选层，但不要把弱命中当唯一真相 |
| adult metadata 源有信息但 BT provider 没资源 | 看起来“懂片子”，但就是下不到 | 资源层与 metadata 层分开设计和测试 |
| 把 helper 站误接成主动 BT provider | 机器人行为和站点现实能力不符 | 在 source registry 层硬性分角 |

### NOT in scope

- 不重做 shared runtime / 非 Telegram 渠道交互。
- 不一次性把所有 adult 站点都做成主动 BT provider。
- 不在这轮扩 `watchlist sync`、`auto-confirm`、非 adult BT 主线。

## Phase 2 — Design Review

### Design scorecard

| Dimension | Score | Notes |
|---|---:|---|
| Relevance-first interaction | 9/10 | 方向正确，核心是让用户先确认“哪一部” |
| Ambiguity handling | 9/10 | 不该默认补年份，应该先给可读候选 |
| Result information density | 8/10 | 海报、标题、类型、年份、一句辅助信息就够了 |
| Telegram readability | 8/10 | 适合做卡片化文本，但不要堆太多字段 |
| adult BT result trust | 8/10 | 资源与信息要同时成立，不能只有其一 |
| Error/fallback clarity | 7/10 | 还需要明确定义“模糊但无高相关结果”的回退 |
| Implementation specificity | 8/10 | 需补清楚 PT / adult BT 各自状态层次 |

### Design findings

1. `High`：PT 搜索需要 3 种结果状态，而不是现在的“命中 or 补年份”两段式。
   - `high-confidence`：1 个主候选 + 1-3 个备选
   - `low-confidence`：3-5 个最相关候选
   - `empty`：明确无结果或建议换关键词
2. `High`：Telegram 卡片要优先展示“让人判断是不是这一部”的字段，而不是下载字段。
   - 先展示：海报 / 标题 / 类型 / 年份 / 别名 / 一句简介
   - 再展示：候选列表 / 数字选择
3. `Medium`：adult BT 卡片必须清楚区分“资源结果”和“metadata 来源”。
   - 资源层字段：站点、做种、大小、磁力
   - metadata 层字段：海报、标题、演员、片商、详情、来源角色
4. `High`：PT 搜索不能在第一轮把“媒体候选确认”和“资源搜索结果”混在一起。
   - 先确认是哪一部作品，再搜索资源，才不会把 `你的名字` 这种强指向标题带偏成一堆扩展资源名。
5. `High`：adult BT 当前用户感知问题不只是“源为空”，还是“卡片排版烂、海报不突出、站点字段未中文化”。
   - 这轮实现必须把 adult card 当成产品面交付，而不只是 formatter 拼文本。
6. `High`：当前 PT 第一轮还在混用资源侧结果做候选，这和用户想要的 MoviePilot 风格相反。
   - 参考 MoviePilot 的交互原则：先做媒体识别/确认，再进入精确资源搜索。
   - Supporting reference:
     - https://deepwiki.com/jxxghp/MoviePilot/3.4-media-recognition
     - https://mattoid.top/docs/moviepilot/search
7. `High`：adult BT “中文化”不能等同于“标签中文化”。
   - 标题、系列、演员必须通过 source-provided 中文字段、多源一致字段或本地 curated alias 生成中文主显示。
   - 日文原名保留为副标题，演员名没有可信中文 alias 时必须标记未确认，不能盲翻。

## Phase 3 — Engineering Review

### Architecture diagram

```text
user query
  -> parse_movie_query()
  -> build_search_request_context()
       -> TMDB candidate search (movie + tv)
       -> query expansion / candidate ranking
       -> Prowlarr search
  -> SearchMediaService.search_and_format()
       -> relevance-ranked media candidates
       -> candidate persistence / selection state
       -> search reply formatter
       -> telegram reply formatter

adult query
  -> BT provider layer
       -> BT_WEB_SOURCES providers
       -> adult Prowlarr indexers
  -> BT display / candidate normalization
  -> metadata/helper layer
       -> avmoo / avbase / jav321 / avsox / caribbeancom / missav / javlibrary / javbus / fanza (role-based)
  -> telegram adult reply formatter
```

### Eng findings

1. `Critical`：当前 `SearchRequestContext` 只有 `lookup_movie_func`，实现名义上已经把搜索空间锁成 movie-first。
   - Fix: 引入统一的 media candidate lookup，至少支持 `movie candidates + tv candidates`，anime 作为候选上的类型/标签处理。
2. `High`：当前 `SearchMediaService` 在高歧义时过早返回 `format_ambiguous_clarification()`。
   - Fix: 改成先排序候选，再基于得分阈值决定是回卡片还是回澄清。
3. `High`：当前电影卡片海报字段是写死占位。
   - Fix: TMDB candidate payload 要真正带 `poster` / `overview` / `media_type` 基础字段。
4. `High`：adult BT 资源层与 metadata/helper 层当前还没有清晰的实现闭环。
   - Fix: 新增 source-role execution map，而不只是 ranking policy。
5. `Medium`：`BT_WEB_SOURCES` 为空时，adult BT 主线几乎必空，但当前用户心智并不接受“配空就空”。
   - Fix: 这是一个需要显式决定的 taste choice，见下方。

### Recommended execution slices

1. Slice A: PT unified media candidate lookup
   - `TmdbClient` 增加统一 candidate 组合入口
   - `SearchRequestContext` 不再只保留 confident movie hit
2. Slice B: PT candidate-first interaction
   - `search_media.py` 第一轮只回媒体候选卡片，不混入资源结果
   - 候选选定后再走资源搜索
   - `你的名字` 这类 query 要强偏置 exact TMDB media match
   - `select <n>` 或数字选择后，再从确认的 `media_identity` 出发触发资源搜索
3. Slice C: adult BT provider completion
   - 明确 active BT provider 列表
   - 确定 `BT_WEB_SOURCES` 为空时策略
   - 让 adult-only 搜索真正拿到 BT 资源
4. Slice D: adult metadata/helper expansion + card redesign
   - 为点名站点实现 role-based helper clients 或 fallback adapters
   - 优先让海报和关键字段在 Telegram 中可读、中文化、可判断
   - 先补高价值主源，再补 supporting / conditional
   - 把资源字段与 metadata 字段做卡片分组，避免“文本很多但没层次”
   - 新增 localization boundary：`search_reply_formatter` 消费可信中文字段，`telegram_reply_formatter` 只展示中文主字段和日文原名副标题

### Failure Modes Registry

| Severity | Failure mode | Prevention |
|---|---|---|
| Critical | 模糊词仍被早早打回“补年份” | relevance threshold 改造 + regression tests |
| Critical | PT 第一轮仍直接返回资源名扩展结果 | 改成媒体候选确认与资源搜索两段式 |
| Critical | 成人站点接了 metadata，但 BT 结果仍空 | provider/helper 双层测试矩阵 |
| High | anime 被错误地硬编码成 movie 或 tv | unified candidate model + explicit media_type display |
| High | 某 metadata 站不稳定拖垮整条 adult 搜索 | fail-closed helper chain + per-source fallback |
| High | adult BT 卡片仍然信息堆叠、海报不显眼、字段不中文化 | Telegram formatter 重构为 poster-first grouped card |
| High | 演员名被机器音译成错误中文名 | 只允许 source alias / curated alias；缺失时标记中文名未确认 |
| Medium | Telegram 卡片字段太多变噪声 | 只保留高判断价值字段 |

### Cross-phase themes

- **Theme: 先确认再选择**
  - CEO 和 Design 都指向同一件事：你要的是“相关候选确认”，不是“搜索参数补全”。
- **Theme: 资源和信息必须同时成立**
  - CEO 和 Eng 都指向同一件事：adult BT 不能只有 metadata，好看但搜不到没有意义。

### Taste decisions surfaced

1. `BT_WEB_SOURCES` 为空时，adult BT 要不要自动启用一组 curated 默认源？
   - Approved: `yes`
   - Why: 当前用户期望是“机器人至少和人手搜一样有基础结果”；完全依赖手工配置会继续制造“网站能搜到、机器人搜不到”的感知断层。
   - Implementation note: 这组默认源必须仍然受 adult-only provider role 约束，不能顺手把 helper 或非 adult provider 混进主动资源搜索层。

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | 不再默认补年份，改为 relevance-first | Mechanical | P1 | 用户价值更完整 | 旧的年份优先澄清 |
| 2 | CEO | `movie / tv / anime` 统一入候选层 | Mechanical | P5 | 避免三套并行逻辑 | 先按类型硬分流 |
| 3 | CEO | adult 站点按 provider/helper 分角 | Mechanical | P4 | 避免职责混乱 | 所有来源都做同一角色 |
| 4 | Design | Telegram 先展示判断字段再展示选择动作 | Mechanical | P5 | 更符合用户确认路径 | 继续以下载字段为主 |
| 5 | Eng | 引入 unified TMDB media candidate lookup | Mechanical | P5 | 当前 movie-first 命名已构成结构性限制 | 继续在 movie lookup 上打补丁 |
| 6 | Eng | `BT_WEB_SOURCES` 为空时建议提供 curated 默认源 | Taste | P1 | 提升 adult BT 实际可用性 | 继续完全手工配置 |
| 7 | Eng | adult metadata 中文化放在 formatter 前的 localization 层 | Mechanical | P5 | 避免 Telegram formatter 硬编码站点翻译逻辑 | 在展示层临时替换日文字段 |

## Completion Summary

- `PT 搜索`：应重构为 **relevance-first candidate confirmation**，而不是 `补年份 first`。
- `TMDB`：需要从“高置信命中才参与”升级为“candidate ranking source + card metadata source”。
- `adult BT`：必须分拆为 `BT provider layer` 和 `metadata/helper layer`；两层都要补齐。
- `当前最大实施风险`：不是 UI，而是把站点角色搞混，最后做出“卡片更好看但资源还是搜不到”的伪完成态。
