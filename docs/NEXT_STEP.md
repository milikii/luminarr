# Next step (v42)

## Current baseline

以下能力已经落地，并且本 step 默认全部保持稳定：

- **控制层**
  - `telegram_updates` 去重
  - `jobs.version + lease_owner + lease_until` 执行所有权
  - downloader / import approval
  - approval timeout
  - confirm wake context rebuild
  - frustration/reset short-circuit
  - callback routing
  - clarification pending restart-durable truth
  - read-only concurrency-safe execution policy

- **媒体主链**
  - `search -> select -> downloader approval -> confirm -> dispatch`
  - `status` / completion-monitor
  - post-download auto import（仍保留 `confirm`）
  - cross-filesystem copy-fallback approval
  - filename normalization
  - metadata scraping（TMDB + Fanart.tv）
  - subtitle auto-translation（当前仅 `.srt`）
  - Emby refresh

- **BT 主链**
  - PT / BT parser-level split
  - 原始磁力 processing-path inquiry baseline
  - BT classification
  - BT `movie / series / anime` TMDB association
  - `raw_bt` destination selection
  - pure BT single-item ranking baseline
  - downloader role binding
  - Transmission + qBittorrent 最小协议执行
  - `btsub list/add/remove/clear/run`
  - BT subscription scheduler tick
  - BT subscription deterministic candidate-selection baseline

## Goal

Land the smallest **BT external web-source baseline**.

## Only do

- 只服务 BT 分流
- 增加最小 `WebSource`
- 第一阶段只允许静态 HTML + 直接 magnet-or-torrent link
- 命中后继续走现有 BT downloader approval-pending 路径
- 保持现有命令词不变：
  - `search/select/status/import/confirm/watchlist/btsub`
- 保持现有媒体后半段边界不变
- 保持现有 PT / BT 分流边界不变
- 保持现有 downloader approval-pending 边界不变
- 保持现有原始磁力 processing-path inquiry 边界不变
- 保持现有 pure BT single-item ranking baseline 不回退

## Do not do

- 不把这一步扩成通用多轮问答框架
- 不把 WebSource 扩成通用站点平台
- 不把 BT 外部网站源引入 PT 主链
- 不引入 BT-only read-only helper
- 不引入通用 scheduler 平台
- 不引入 automatic `confirm`
- 不新增下载器 / 媒体服务器支持
- 不改现有 downloader/import approval 协议
- 不改 `btsub` 已落地的共享选源逻辑
- 不改原始磁力处理链问询的既有形状

## Done when

- BT 分流已能在 Prowlarr 之外接入最小 WebSource
- WebSource 结果经过最小确定性清洗后仍继续走既有 approval-pending 路径
- 现有 Telegram 命令行为不回退
- 现有 downloader/import approval 行为不回退
- 现有 BT follow-up、原始磁力 processing-path inquiry、qB 执行、`btsub` 共享选源、pure BT 单片优选、raw_bt 非媒体边界都不回退
- 现有 metadata / subtitle / refresh 链路不回退

## After this step

按顺序继续：

1. 最小 BT-only read-only helper baseline
   - 仅手动探索 / 站点规则维护辅助
   - 只读
   - 不得进入 scheduler truth / approval truth / direct dispatch
2. 渠道扩展
   - Feishu / WeCom / personal WeChat
3. 运维清理
   - downloader/library asset correlation and cleanup
