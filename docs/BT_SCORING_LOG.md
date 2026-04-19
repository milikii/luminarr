# BT scoring log (v1)

> 目的：承接当前“BT 共享确定性评分器”主线的详细闭环。
> 约束：蓝图继续看 `docs/BT_SCORING_PLAN.md`；`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 当前主线状态：进行中；2026-04-19 已完成 Phase 1 和 Phase 2 基线，`.venv/bin/python -m pytest -q tests/test_bt_candidate_scorer.py` 得到通过，当前最小下一步切到 Phase 3 接 `pure_bt.py`。
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
- 三条 BT 路径还没真正调用共享评分器，当前只是把 helper 和测试基线先落稳。

### 2.2 规则文件加载

已完成闭环：
- 已新增 `app/services/bt_scoring_rules.yml`，把当前默认权重、分辨率、片源、编码和字幕组偏好显式写回仓库。
- 已在 `app/services/bt_candidate_scorer.py` 增加 `load_bt_scoring_rules()`；文件缺失、段落类型不对、字段不是数字时会打印中文 warning，并继续使用内置默认值。
- 已在 `tests/test_bt_candidate_scorer.py` 补规则文件读取、自定义权重生效、缺文件回退和坏字段回退四类测试。

当前风险：
- `pure_bt.py`、`manage_bt_subscription.py` 和媒体型 BT 候选展示还没真正消费这份规则文件。

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_bt_candidate_scorer.py`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 新闭环优先按 2.1~2.3 合并；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 当前主线完成后，在 `docs/NEXT_STEP.md`、`docs/STATUS.md` 和 `docs/INDEX.md` 同步切到下一项。
