# Next step (v41)

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
  - downloader role binding
  - Transmission + qBittorrent 最小协议执行
  - `btsub list/add/remove/clear/run`
  - BT subscription scheduler tick
  - BT subscription deterministic candidate-selection baseline

## Goal

Land the smallest **pure BT single-item ranking baseline**.

## Only do

- 只服务 `纯 BT 下载链`
- 对单个资源候选做最小确定性预过滤
- 只围绕“单片资源规格是否足够出色”做最小优选
- 命中后继续走现有 BT downloader approval-pending 路径
- 保持现有命令词不变：
  - `search/select/status/import/confirm/watchlist/btsub`
- 保持现有媒体后半段边界不变
- 保持现有 PT / BT 分流边界不变
- 保持现有 downloader approval-pending 边界不变
- 保持现有原始磁力 processing-path inquiry 边界不变

## Do not do

- 不把这一步扩成通用多轮问答框架
- 不把 pure BT 优选和影视入库链规则混成一套
- 不引入 BT external website sources
- 不引入 BT-only read-only helper
- 不引入通用 scheduler 平台
- 不引入 automatic `confirm`
- 不新增下载器 / 媒体服务器支持
- 不改现有 downloader/import approval 协议
- 不改 `btsub` 已落地的共享选源逻辑
- 不改原始磁力处理链问询的既有形状

## Done when

- pure BT 下载链不再盲目接受任意单片资源
- pure BT 单片候选有最小确定性预过滤 / 优选
- 命中后仍继续走既有 approval-pending 路径
- 现有 Telegram 命令行为不回退
- 现有 downloader/import approval 行为不回退
- 现有 BT follow-up、原始磁力 processing-path inquiry、qB 执行、`btsub` 共享选源、raw_bt 非媒体边界都不回退
- 现有 metadata / subtitle / refresh 链路不回退

## After this step

按顺序继续：

1. 最小 BT external web-source baseline
   - `Prowlarr + WebSource`
   - 仅 BT 使用
   - 仅静态 HTML / 直接 magnet-or-torrent link
   - 命中后继续走现有 approval-pending 路径
2. 最小 BT-only read-only helper baseline
   - 仅手动探索 / 站点规则维护辅助
   - 只读
   - 不得进入 scheduler truth / approval truth / direct dispatch
3. 渠道扩展
   - Feishu / WeCom / personal WeChat
4. 运维清理
   - downloader/library asset correlation and cleanup
