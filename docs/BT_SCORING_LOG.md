# BT scoring log (v2)

> 目的：承接当前“BT 共享确定性评分器”主线的详细闭环。
> 约束：蓝图继续看 `docs/BT_SCORING_PLAN.md`；`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 当前主线状态：已完成；2026-04-19 已完成 Phase 1~5，三条 BT 路径都已接入共享评分器，`.venv/bin/python -m pytest -q tests/test_bt_candidate_scorer.py tests/test_pure_bt.py tests/test_manage_bt_subscription.py` 得到 `62 passed`，主线已满足 `docs/NEXT_STEP.md` 退出条件 1。
- 上一条已完成主线“最小人类可用入口继续补齐”继续看 `docs/QUICK_START_PLAN.md` 与 `docs/DEPLOY_CHECKLIST.md`。
- 当前这一步的设计蓝图、Phase 顺序和退出条件统一看 `docs/BT_SCORING_PLAN.md`。

## 2. Risk groups

### 2.1 统一候选结构 / 预过滤 / 评分输出

已完成闭环：
- 已新增 `app/services/bt_candidate_scorer.py`，落下 `BTCandidate`、`BTScoringContext`、`ScoredCandidate` 和内置最小规则集。
- 已把标题命中、链接合法性、重复 `infohash`、低质量黑名单、single-item 合集过滤收进统一预过滤。
- 已把分辨率、片源、做种数、体积区间、编码和字幕组偏好收进统一打分输出，`pick_best()` 只会从未被 drop 的候选里取第一名。
- 已新增 `tests/test_bt_candidate_scorer.py`，先锁 15 条典型候选场景，覆盖 drop reason、排序、score breakdown 和 `movie/anime/raw_bt` 三种上下文差异。

当前风险：
- 规则文件虽然已接进来，但当前只支持项目里约定的最小 YAML 子集；后续改文件时必须守住现有键名和两空格缩进。
- 媒体型 BT 候选展示还没真正调用共享评分器。

### 2.2 规则文件加载

已完成闭环：
- 已新增 `app/services/bt_scoring_rules.yml`，把当前默认权重、分辨率、片源、编码和字幕组偏好显式写回仓库。
- 已在 `app/services/bt_candidate_scorer.py` 增加 `load_bt_scoring_rules()`；文件缺失、段落类型不对、字段不是数字时会打印中文 warning，并继续使用内置默认值。
- 已在 `tests/test_bt_candidate_scorer.py` 补规则文件读取、自定义权重生效、缺文件回退和坏字段回退四类测试。

当前风险：
- 媒体型 BT 候选展示还没真正消费这份规则文件。

### 2.3 `pure_bt.py` 接线

已完成闭环：
- 已把 `app/services/pure_bt.py` 的单片优选改成走 `bt_candidate_scorer.pick_best()`；纯 BT 路径不再自己维护一套分辨率/做种数排序。
- 已补 `tests/test_pure_bt.py`，覆盖文本提取、低质量/合集过滤、共享评分器默认排序和自定义规则生效。
- 现有 Telegram 纯 BT 入口 focused case 继续通过，说明目的地选择入口和服务未就绪保护没有回退。

当前风险：
- 媒体型 BT 候选展示排序还没切到共享评分器；Phase 5 还没开始。

### 2.4 `manage_bt_subscription.py` 接线

已完成闭环：
- 已把 `app/services/manage_bt_subscription.py::_scan_chat_once()` 的订阅选源切到 `bt_candidate_scorer.pick_best()`；当前复用共享低质量过滤和评分排序，不改待确认创建、`last_seen` 回写或 scheduler tick 协议。
- 订阅扫描上下文当前故意不额外启用标题命中过滤：`btsub` 常见输入是中文订阅名，但来源站点可能返回英文标题；这一步只替换排序，不把中英混合站点结果误判成“当前没有新资源”。
- 已补 `tests/test_manage_bt_subscription.py`，覆盖默认排序、`last_seen` 跳过、scheduler tick 复用和自定义评分规则生效。

当前风险：
- 媒体型 BT 候选展示仍未按共享评分器排序，当前主线还差最后一条 BT 路径。

### 2.5 媒体型 BT 候选展示排序

已完成闭环：
- 已把 `app/services/search_media.py` 的媒体型 BT 候选展示切到共享评分器排序；候选会先按统一 drop/filter/score 规则重排，再按相同顺序写进进程内缓存和 `candidate_mapping`，保证用户看到的编号和后续 `select <编号>` 读取的是同一份真相。
- 已让 `search_request_context.py` 额外回传实际命中的搜索 query，排序阶段直接复用这条 query，避免 TMDB 英文命中和原始中文输入混在一起时误用错误的匹配基准。
- 已补 `tests/test_search_media.py`，锁住“共享规则会改展示顺序，而且缓存顺序跟着一起变”的 focused case。

当前风险：
- BT 评分器主线已完成；后续风险转移到下一条 `Jellyfin / Plex` 主线，不再继续在这条线拆微分流。

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_bt_candidate_scorer.py`
- `.venv/bin/python -m pytest -q tests/test_pure_bt.py`
- `.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py`
- `.venv/bin/python -m pytest -q tests/test_search_media.py`
- `.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "handle_message_bt_processing_path_pure_bt_choice_routes_to_destination_prompt or enter_pure_bt_flow_returns_service_not_ready_when_destination_persist_fails"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 新闭环优先按 2.1~2.4 合并；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 当前主线完成后，在 `docs/NEXT_STEP.md`、`docs/STATUS.md` 和 `docs/INDEX.md` 同步切到下一项。
