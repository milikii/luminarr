# Next step (v216)

## Current goal

- 当前唯一主线：**BT 共享确定性评分器**（2026-04-19 已完成 quick start 主线：`docs/DEPLOY_CHECKLIST.md` 覆盖 `Phase 0-6`、`.env.example` 已按分组重构、README §0 已加 checklist 指针，满足旧主线 `Done when` 第 1 条后切到本线）
- 刚完成主线：**最小人类可用入口继续补齐已完成**；部署蓝图继续看 `docs/QUICK_START_PLAN.md`，交付物继续看 `docs/DEPLOY_CHECKLIST.md`
- 上一条完成主线：**shared private-chat 交付体验收口已完成**；详细闭环继续写在 `docs/SHARED_DELIVERY_UX_LOG.md`
- 再上一条完成主线：**`series / anime` 独立名称解析最小实现已完成**；详细闭环继续写在 `docs/SERIES_ANIME_NAMING_LOG.md`
- 更早完成主线：**`cleanup_downloaded_source.py` cleanup 编排层瘦身 / 模块化已完成**；详细闭环继续写在 `docs/CLEANUP_SLIMMING_LOG.md`
- 更早完成主线：`app/main.py` / `private_chat_runtime.py` / cleanup / BT 订阅 / search / add / import / telegram 渠道层瘦身、下载完成轮询、Feishu 风险收口、持久化吞错收口都保持完成态，不回退
- 当前最小闭环：按 `docs/BT_SCORING_PLAN.md` Phase 4 把 `manage_bt_subscription.py::_scan_chat_once()` 的选源切到共享评分器，先只替换排序，不动待确认创建、`last_seen` 或 scheduler tick 协议
- 当前主线蓝图统一写在 `docs/BT_SCORING_PLAN.md`

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- 当前主线蓝图：`docs/BT_SCORING_PLAN.md`
- 刚完成主线蓝图 / 交付物：`docs/QUICK_START_PLAN.md`、`docs/DEPLOY_CHECKLIST.md`
- 更早主线台账：`docs/SHARED_DELIVERY_UX_LOG.md`、`docs/SERIES_ANIME_NAMING_LOG.md`、`docs/APP_MAIN_SLIMMING_LOG.md`、`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`、`docs/CLEANUP_SLIMMING_LOG.md`、`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`、`docs/SEARCH_MEDIA_SLIMMING_LOG.md`、`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`、`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`、`docs/TELEGRAM_BOT_SLIMMING_LOG.md`、`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`、`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`、`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`、`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成窗口证据：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- 知识入口：`README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md`

## Only do

- 只推进 BT 共享确定性评分器的一个最小 Phase；每轮只做一个最小闭环，不顺手改 approval、dispatch、import、cleanup 或 workflow 真相
- 当前优先交付：
  - `app/services/bt_candidate_scorer.py`
  - `tests/test_bt_candidate_scorer.py`
  - `app/services/bt_scoring_rules.yml`
  - 后续按顺序接到 `pure_bt.py`、`manage_bt_subscription.py`、媒体型 BT 候选排序
- 保持 Telegram / personal WeChat / Feishu / WeCom 四渠道共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 保持 cleanup / search / approval / import / status / watchlist / btsub 既有协议和 guardrail 不回退
- 文档继续分层：`STATUS.md` 只保留当前快照，`BT_SCORING_PLAN.md` 承接当前主线蓝图，`QUICK_START_PLAN.md` / `DEPLOY_CHECKLIST.md` 保持刚完成部署主线的蓝图与交付物定位，其余完成台账继续只作历史闭环入口
- 保持 cleanup 完成态证据、docs gate、quick start 完成态和 shared delivery 完成态结论稳定，不回退成“仍在进行中”

## Do not do

- 不引入 DSL / 通用规则语言 / LLM 判分
- 不放宽现有 pending state gate、approval、`jobs` / `job_event` / lease/version / SQLite 真相边界
- 不在这一步引入自动 `confirm`、自动下载、新 workflow、Jellyfin / Plex 支持或其他新集成
- 不把这一步变成站点白名单平台、偏好学习器或自动 confirm 一条龙

## Done when

当前主线视为 **已基本完成**，触发以下任一可测量条件即停止，并通知用户切到下面 `After this step` 第 1 项：

1. 三条 BT 路径都已接入共享评分器，`.venv/bin/python -m pytest -q tests/test_bt_candidate_scorer.py tests/test_pure_bt.py tests/test_manage_bt_subscription.py` 全绿；
2. 或者本轮代码变更 `< 20` 行、只是为同一个 weight key 再加一条微调，触发 `AGENTS.md §11` 停机规则。

附加约束（不算退出条件，只是不得违反）：

- 四渠道现有 cleanup / search / approval / import / status / watchlist / btsub 协议不回退
- `verification docs gate` 与 cleanup 完成态证据持续通过
- `docs/STATUS.md` / `docs/NEXT_STEP.md` / `README.md` / `docs/BT_SCORING_PLAN.md` / `docs/QUICK_START_PLAN.md` / `docs/DEPLOY_CHECKLIST.md` / 其余完成台账继续保持分层一致，不重新写回长台账

## After this step

1. Jellyfin / Plex 支持（后续）
2. plugin 体系继续后置
