# Next step (v44)

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
  - BT shared source adapter baseline（`Prowlarr + WebSource`）
  - BT external web-source baseline（仅静态 HTML + 直接 magnet / torrent link）
  - BT-only read-only helper baseline（`bt搜 <关键词>` / `bt search <关键词>`）
  - downloader role binding
  - Transmission + qBittorrent 最小协议执行
  - `btsub list/add/remove/clear/run`
  - BT subscription scheduler tick
  - BT subscription deterministic candidate-selection baseline

## Goal

Land the smallest **richer BT WebSource site-rule / metadata extraction baseline**.

## Only do

- 只服务 BT 分流
- 在现有内建 WebSource 规则上补最小确定性字段抽取增强
- 增强目标只限共享 BT 来源适配已使用的字段：
  - `title`
  - `source`
  - `seeders`
  - `size`
  - `indexer / sourceProvider`
- pure BT、`btsub`、BT-only read-only helper 必须继续复用同一个共享 BT 来源适配入口
- 输出仍必须是确定性的结构化候选，不得写主 workflow 真相
- 保持现有命令词不变：
  - `search/select/status/import/confirm/watchlist/btsub`
  - `bt搜 <关键词>` / `bt search <关键词>`
- 保持现有媒体后半段边界不变
- 保持现有 PT / BT 分流边界不变
- 保持现有 downloader approval-pending 边界不变
- 保持现有原始磁力 processing-path inquiry 边界不变
- 保持现有 pure BT single-item ranking baseline 不回退
- 保持现有 BT external web-source baseline 不回退
- 保持现有 BT-only read-only helper baseline 不回退

## Do not do

- 不把这一步扩成通用多轮问答框架
- 不把 WebSource 规则层或 helper 扩成通用 skill / agent 平台
- 不把 BT 来源适配层扩成 PT / BT 通用搜索平台
- 不让站点规则增强去写数据库、approval、jobs、lease 或任何 workflow truth
- 不让 helper 或 WebSource 规则直接 dispatch 下载器
- 不让 helper 或 WebSource 规则直接触发 import / refresh / 任何副作用
- 不把 BT 外部网站源或 helper 引入 PT 主链
- 不引入新的站点平台化 DSL、通用浏览器自动化或 JS 渲染
- 不引入通用 scheduler 平台
- 不引入 automatic `confirm`
- 不新增下载器 / 媒体服务器支持
- 不改现有 downloader/import approval 协议
- 不改 `btsub` 已落地的共享选源逻辑
- 不改原始磁力处理链问询的既有形状
- 不让 scheduler tick、`btsub run`、恢复逻辑依赖 helper 或 richer rule path 之外的新运行时能力

## Done when

- 至少一个现有内建 WebSource 已能稳定抽出更丰富的结构化字段
- richer 字段已通过现有 `Prowlarr + WebSource` 共享 BT 来源适配入口进入 BT 支线
- pure BT、`btsub`、BT-only read-only helper 都没有因为 richer 字段增强而回退
- 站点规则增强保持只读，不写数据库、不改 approval、不改 jobs、不触发 dispatch
- 现有 Telegram 命令行为不回退
- 现有 downloader/import approval 行为不回退
- 现有 BT follow-up、原始磁力 processing-path inquiry、qB 执行、`btsub` 共享选源、pure BT 单片优选、BT external web-source、BT-only read-only helper、raw_bt 非媒体边界都不回退
- 现有 metadata / subtitle / refresh 链路不回退

## After this step

按顺序继续：

1. 渠道扩展
   - Feishu / WeCom / personal WeChat
2. 运维清理
   - downloader/library asset correlation and cleanup
