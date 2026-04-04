# Next step (v40)

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
  - BT classification
  - BT `movie / series / anime` TMDB association
  - `raw_bt` destination selection
  - downloader role binding
  - Transmission + qBittorrent 最小协议执行
  - `btsub list/add/remove/clear/run`
  - BT subscription scheduler tick
  - BT subscription deterministic candidate-selection baseline

## Goal

Land the smallest **original magnet processing-path inquiry baseline**.

## Only do

- 当用户直接发送 `magnet:?` 或明确要求“下载这个 BT / 磁力”时，仍先进入 BT 支线
- 在该入口只增加一个最小问询：
  - `影视入库链`
  - `纯 BT 下载链`
- 不再从用户视角重复问“PT 还是 BT”
- 选择 `影视入库链` 后，继续进入现有媒体型 BT 流程
- 选择 `纯 BT 下载链` 后，继续进入现有 `raw_bt` / 纯 BT 流程
- 保持现有命令词不变：
  - `search/select/status/import/confirm/watchlist/btsub`
- 保持现有媒体后半段边界不变
- 保持现有 PT / BT 分流边界不变
- 保持现有 downloader approval-pending 边界不变

## Do not do

- 不把这一步扩成通用多轮问答框架
- 不在这一步落地 pure BT 单片优选
- 不引入 BT external website sources
- 不引入 BT-only read-only helper
- 不引入通用 scheduler 平台
- 不引入 automatic `confirm`
- 不新增下载器 / 媒体服务器支持
- 不改现有 downloader/import approval 协议
- 不改 `btsub` 已落地的共享选源逻辑

## Done when

- 原始 `magnet:?` / 直接 BT 下载入口会先问“影视入库链 / 纯 BT 下载链”
- 用户视角不再被重复追问“PT 还是 BT”
- 选择 `影视入库链` 后仍进入既有媒体型 BT follow-up
- 选择 `纯 BT 下载链` 后仍留在既有 `raw_bt` / 纯 BT 边界
- 现有 Telegram 命令行为不回退
- 现有 downloader/import approval 行为不回退
- 现有 BT follow-up、qB 执行、`btsub` 共享选源、raw_bt 非媒体边界都不回退
- 现有 metadata / subtitle / refresh 链路不回退

## After this step

按顺序继续：

1. 最小 pure BT 单片优选 baseline
   - 只服务纯 BT 下载链
   - 不复用影视入库链的复杂规则
   - 先确定性预过滤，再决定是否接 LLM 辅助优选
2. 最小 BT external web-source baseline
   - `Prowlarr + WebSource`
   - 仅 BT 使用
   - 仅静态 HTML / 直接 magnet-or-torrent link
   - 命中后继续走现有 approval-pending 路径
3. 最小 BT-only read-only helper baseline
   - 仅手动探索 / 站点规则维护辅助
   - 只读
   - 不得进入 scheduler truth / approval truth / direct dispatch
4. 渠道扩展
   - Feishu / WeCom / personal WeChat
5. 运维清理
   - downloader/library asset correlation and cleanup
