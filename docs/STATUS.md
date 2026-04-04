# Current status (v40)

## Project position

Luminarr 当前是一个 **Telegram 私聊唯一入口** 的垂直影视自动化 Harness。

当前固定主线：
- Telegram
- TMDB
- Prowlarr（当前已实现来源）
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
  - BT classification（`movie / series / anime / raw_bt`）
  - BT `movie / series / anime` TMDB association
  - `raw_bt` destination selection
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
  - 原始磁力“处理链”问询 baseline（`影视入库链 / 纯 BT 下载链`）

- **后续 BT 路线**
  - pure BT 单片优选 baseline（不复用影视入库链复杂规则）
  - BT external web-source baseline（`Prowlarr + WebSource`，仅 BT 使用）
  - BT-only read-only helper baseline（仅手动探索 / 站点规则维护辅助）

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
- subtitle auto-translation 目前只处理现成 `.srt`，还不支持“从视频里提取英文字幕轨”
- `FANART_API_KEY`、`SUBTITLE_TRANSLATION_API_KEY`、Emby 配置缺失时，相关增强链会失败但不回滚 import success
- 原始磁力入口当前仍直接进入现有 BT 分类链，尚未补“影视入库链 / 纯 BT 下载链”问询
- pure BT 当前还没有“单片资源规格优选”能力
- BT external web-source 和 BT-only read-only helper 还没落地

## Latest verification

- tests: `191 passed` (`.venv/bin/python -m pytest -q`)
- focused tests: `5 passed` (`.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py`)
- manual verification:
  - qBittorrent protocol baseline passed
  - BT subscription baseline passed
  - BT subscription scheduler-tick baseline passed
  - BT subscription deterministic candidate-selection baseline passed

## Current priority

当前只做一件事：

- 为原始 `magnet:?` / 直接 BT 下载入口补最小“处理链”问询，不重复问 PT / BT。
