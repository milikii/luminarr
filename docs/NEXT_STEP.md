# Next step (v45)

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
  - BT WebSource richer metadata extraction baseline（当前内建 `nyaa` 已补 `size + seeders`）
  - BT-only read-only helper baseline（`bt搜 <关键词>` / `bt search <关键词>`）
  - downloader role binding
  - Transmission + qBittorrent 最小协议执行
  - `btsub list/add/remove/clear/run`
  - BT subscription scheduler tick
  - BT subscription deterministic candidate-selection baseline

## Goal

Land the smallest **Feishu private-chat adapter baseline**.

## Only do

- 只加 Feishu 私聊单聊入口
- 继续复用现有 workflow 和 service：
  - `search_media`
  - `add_to_downloader`
  - `get_download_status`
  - `import_to_library`
  - `manage_watchlist`
  - `manage_bt_subscription`
- 保持现有自然语言 / 文本协议形状尽量不变：
  - `search/select/status/import/confirm/watchlist/btsub`
  - `bt搜 <关键词>` / `bt search <关键词>`
- 继续复用现有 downloader / import approval 边界
- 继续复用现有 BT 分流、原始磁力 processing-path inquiry、pure BT、`btsub`、BT-only read-only helper
- 只做最小私聊收发适配，不做群聊
- 保持现有媒体后半段边界不变
- 保持现有 PT / BT 分流边界不变
- 保持现有 downloader approval-pending 边界不变

## Do not do

- 不把这一步扩成通用多轮问答框架
- 不把 Feishu 适配扩成通用多渠道平台
- 不同时做 WeCom / personal WeChat
- 不改现有 SQLite / approval / jobs / lease 真相协议
- 不改现有 downloader / import approval 协议
- 不改现有 BT shared source adapter、WebSource 规则层、`btsub` 共享选源逻辑
- 不改现有原始磁力处理链问询形状
- 不引入群聊、机器人平台化中间层、通用 webhook 总线
- 不引入通用 scheduler 平台
- 不引入 automatic `confirm`
- 不新增下载器 / 媒体服务器支持
- 不让 scheduler tick、`btsub run`、恢复逻辑依赖 Feishu 适配

## Done when

- Feishu 私聊已能进入现有主链的最小可用命令集合
- 现有 service、approval、jobs、lease 真相边界保持不变
- Telegram 行为不回退
- 现有 downloader/import approval 行为不回退
- 现有 BT follow-up、原始磁力 processing-path inquiry、qB 执行、`btsub` 共享选源、pure BT 单片优选、BT external web-source、BT WebSource richer metadata extraction、BT-only read-only helper、raw_bt 非媒体边界都不回退
- 现有 metadata / subtitle / refresh 链路不回退

## After this step

按顺序继续：

1. 渠道扩展
   - WeCom / personal WeChat
2. 运维清理
   - downloader/library asset correlation and cleanup
