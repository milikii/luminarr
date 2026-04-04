# Current status (v43)

## Project position

Luminarr 当前是一个 **Telegram 私聊唯一入口** 的垂直影视自动化 Harness。

当前固定主线：
- Telegram
- TMDB
- Prowlarr（当前主来源）+ 最小 BT WebSource（仅 BT 使用）
- Transmission + qBittorrent
- Emby
- SQLite
- Docker Compose
- 单实例 / 单进程 / 单机
- movie-first

## What is implemented now

- **控制层**
  - Telegram runtime
  - `telegram_updates` 去重
  - `jobs` 执行所有权
  - approval / lease / replay guard
  - approval timeout
  - confirm wake context rebuild
  - frustration/reset short-circuit
  - callback routing
  - clarification restart-durable truth
  - read-only concurrency-safe execution policy

- **媒体主链**
  - `search_media`
  - TMDB-first 搜索 + 候选映射持久化
  - downloader approval / `confirm`
  - `status`
  - `import` approval / `confirm`
  - hardlink import
  - cross-filesystem copy-fallback approval
  - completion-monitor
  - post-download auto import（仍保留 `confirm`）
  - filename normalization
  - metadata scraping（TMDB + Fanart.tv）
  - subtitle auto-translation（当前仅 `.srt`）
  - Emby refresh

- **BT 主链**
  - PT / BT parser-level split
  - 原始磁力 processing-path inquiry baseline（`影视入库链 / 纯 BT 下载链`）
  - BT classification（`movie / series / anime / raw_bt`）
  - BT `movie / series / anime` TMDB association
  - `raw_bt` destination selection
  - pure BT single-item ranking baseline（文本型 `下载这个 BT <查询词>` 走最小确定性预过滤 / 优选后进入既有 downloader approval）
  - BT shared source adapter baseline（`Prowlarr + WebSource` 共用候选字段归一化、最小清洗和去重入口）
  - BT external web-source baseline（当前最小站点源为静态 HTML + 直接 magnet / torrent link，且只服务 BT 分流）
  - downloader role binding
  - BT dispatch / transfer execution
  - qBittorrent 最小协议执行（add / status / import-source）
  - BT subscription manual baseline
  - BT subscription scheduler tick baseline
  - BT subscription deterministic candidate-selection baseline

- **其他业务面**
  - `watchlist` 手动持久化基线
  - `watchlist` 的 `movie / series / anime` 分类真相

## What is not implemented yet

- **当前 next step**
  - BT-only read-only helper baseline（仅手动探索 / 站点规则维护辅助）

- **后续 BT 路线**
  - richer WebSource site rules / metadata extraction（当前仍只做最小静态页面与直接链接）

- **后续渠道**
  - Feishu
  - WeCom
  - personal WeChat

- **后续运维**
  - downloader/library asset correlation and cleanup

- **仍未解决的基础能力**
  - real image/media poster rendering
  - multi-process/global locking semantics

## Current risks

- poster-card 仍然是文本基线
- candidate mapping 仍只保留每个 chat 最近一次搜索窗口
- completion truth 主要依赖 runtime 观察，不是完整独立后台轮询平台
- BT subscription 当前已从“盲拿第一个结果”收紧到共享确定性选源，但仍不是完整质量评分 / 规则引擎
- BT shared source adapter 已接 `Prowlarr + WebSource`，但当前 WebSource 仍只是最小静态 HTML 基线；站点规则、字段抽取和链接校验还不丰富
- 原始磁力入口当前已先问“影视入库链 / 纯 BT 下载链”，但为兼容旧 follow-up，仍接受 `movie/series/anime/raw_bt` 旧回复捷径
- subtitle auto-translation 目前只处理现成 `.srt`，还不支持“从视频里提取英文字幕轨”
- `FANART_API_KEY`、`SUBTITLE_TRANSLATION_API_KEY`、Emby 配置缺失时，相关增强链会失败但不回滚 import success
- pure BT 当前已落地最小确定性单片优选，但仍只覆盖文本型 `下载这个 BT <查询词>`，还不是完整质量评分 / 规则引擎
- BT-only read-only helper 还没落地
- `BT_WEB_SOURCES` 当前只做最小来源开关；首批内建站点仍很少，失败时会显式日志提示但不会自动修复站点规则

## Latest verification

- tests: `198 passed` (`.venv/bin/python -m pytest -q`)
- focused tests: `22 passed` (`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_manage_bt_subscription.py tests/test_config.py`)
- focused tests: `14 passed` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "bt_processing_path or bt_classification_reply_when_pending or bt_raw_classification_reply_when_pending or bt_tmdb_association_succeeds_for_movie or raw_bt_destination_selection_succeeds or callback_query_magnet_routes_to_bt_direct_split or callback_query_bt_classification_reply_when_pending or callback_query_raw_bt_destination_selection_succeeds or bt_classification_pending_survives_restart or bt_tmdb_association_pending_survives_restart or raw_bt_destination_pending_survives_restart or bt_classification_cancel_when_pending or bt_classification_pending_returns_reminder_for_plain_text"`)
- manual verification:
  - qBittorrent protocol baseline passed
  - BT subscription baseline passed
  - BT subscription scheduler-tick baseline passed
  - BT subscription deterministic candidate-selection baseline passed
  - original magnet processing-path inquiry baseline passed
  - pure BT single-item ranking baseline passed
  - BT external web-source baseline passed

## Current priority

当前只做一件事：

- 为 BT 分流补最小 BT-only read-only helper baseline，严格保持只读边界，不写 workflow truth，不碰既有 approval / dispatch 路径。
