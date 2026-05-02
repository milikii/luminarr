# investigate: telegram candidate relevance pollution

## Goal

修复 Telegram 候选确认里的作品相关性污染问题。当前短中文查询（例如 `超人`）会把明显不该进入首屏候选的跨作品结果混进来，例如 `女超人`、`一拳超人`。本任务目标是收紧候选相关性，让“明确 franchise/主标题意图”的查询先返回同一作品家族，而不是保留过宽的 contains 扩散。

## Symptoms

* 用户在 Telegram 实测里确认：候选海报卡片效果变好了，但候选搜索逻辑仍然离谱。
* 现象示例：查询 `超人` 时，候选里混入 `女超人`、`一拳超人`，并带出不符合当前意图的历史/旁支结果。
* 这个问题在卡片化之前就存在，本轮只是因为视觉更明显而暴露得更直接。

## What I already know

* 根因复现实验已确认：
  * `超人` -> `超人(2025)` relation=`exact`
  * `超人前传` relation=`prefix`
  * `女超人` / `一拳超人` relation=`contains`
  * 当前 `_rank_tmdb_candidates()` 会把 contains 项保留进最终 top-N。
* 当前短中文标题的“保留候选广度”逻辑来自 `app/search_title_normalization.py` 中的 `should_preserve_short_query_candidate_spread()` / `resolve_short_query_contains_slots()`。
* 当前 franchise intent 规则只覆盖《魔戒》；`app/search_franchise_intent.py` 没有 `超人` / `superman` 相关规则。

## Root Cause Hypothesis

* 对 `超人` 这类短中文查询，系统把 `contains` 当成合理扩展候选。
* 同时缺少 `超人` 这类高价值 franchise 的显式保护，导致 `女超人`、`一拳超人` 不能被排除在首屏候选之外。

## Requirements

* 修复 `超人` 这类明确 franchise 查询的候选污染。
* 首屏候选应优先保留 `超人` 同一作品家族结果，不应混入 `女超人`、`一拳超人` 这类跨 franchise contains 项。
* 在同一 franchise / 同一主标题家族内部，候选排序应显式参考 TMDB 指标，而不是依赖当前隐式返回顺序。
* 同家族排序优先级收口为：`popularity` -> `vote_average` -> `vote_count`（均为 TMDB 值，降序）。
* 不改 Telegram 候选卡片展示层。
* 不重写整套 TMDB 排序器；优先做最小、可验证的相关性收敛。

## Acceptance Criteria

* [ ] 本地复现中，`超人` 查询不再把 `女超人`、`一拳超人` 放进首屏候选。
* [ ] `超人` 查询仍能保留同一主标题家族的合理候选，例如新版/老版/前传。
* [ ] 同家族候选的内部顺序由 TMDB 指标显式决定，而不是依赖当前 API 返回顺序。
* [ ] 现有 `传奇` / `丧尸` / `Dune 2021` 等已有覆盖样例不发生无意回退。
* [ ] 相关测试补齐并通过。

## Out of Scope

* 全量重构 TMDB 相关性打分器
* 一次性清洗所有中文短词查询策略
* 改动资源搜索、审批、导入主线

## Technical Notes

* 重点文件：
  * `app/clients/tmdb.py`
  * `app/search_franchise_intent.py`
  * `app/search_title_normalization.py`
  * `tests/test_search_media.py`
