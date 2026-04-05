# Next step (v53)

## Current baseline

以下能力已经落地，并且本 step 默认全部保持稳定：

- **控制层**
  - shared private-chat text runtime baseline（Telegram 继续走原路径，非 Telegram 私聊适配可复用同一文本分发入口）
  - Feishu private-chat identity projection + text event adapter baseline（已能把 Feishu 私聊文本事件压成现有 `query/chat/user/reply` 入口）
  - Feishu private-chat adapter baseline（最小 webhook 请求入口 + 文本回消息已接上）
  - Feishu webhook event-signature verification baseline（非 `url_verification` 请求已先验签）
  - WeCom private-chat decrypted-text adapter kernel baseline（已能解析最小已解密 XML 私聊文本消息，并把 `FromUserName` 投影到现有整数 `chat_id/user_id` 后进入 shared private-chat text runtime）
  - WeCom callback envelope + text reply baseline（已能完成 callback GET URL 校验、POST 验签解密入站，并按最小加密被动文本回包返回到原私聊）
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

Continue the smallest remaining Telegram media sending step for later QR/file handoff.

## Only do

- 只补 Telegram 最小图片/文件发送 baseline
- 目标只服务后续 personal WeChat 二维码登录等最小媒资回传
- 继续复用当前 Telegram runtime、Application 和既有管理员私聊入口
- 保持现有自然语言 / 文本协议形状不变：
  - `search/select/status/import/confirm/watchlist/btsub`
  - `bt搜 <关键词>` / `bt search <关键词>`
- 保持 shared private-chat text runtime 的文本分发边界不变
- 保持现有 workflow 和 service 真相边界不变：
  - `search_media`
  - `add_to_downloader`
  - `get_download_status`
  - `import_to_library`
  - `manage_watchlist`
  - `manage_bt_subscription`
- 继续复用现有 downloader / import approval 边界
- 继续复用现有 BT 分流、原始磁力 processing-path inquiry、pure BT、`btsub`、BT-only read-only helper
- 只补“发图片 / 发文件”能力，不补新的富文本协议

## Do not do

- 不同时做 personal WeChat 接入
- 不把这一步扩成 Telegram 卡片 UI overhaul
- 不补群聊、频道、相册、按钮、内联富交互
- 不改 shared private-chat text runtime 的既有文本协议形状
- 不改现有 SQLite / approval / jobs / lease 真相协议
- 不改现有 downloader / import approval 协议
- 不改现有 BT shared source adapter、WebSource 规则层、`btsub` 共享选源逻辑
- 不改现有原始磁力处理链问询形状
- 不引入通用多渠道媒资抽象层
- 不引入通用文件资产服务、对象存储或 CDN
- 不引入 automatic `confirm`
- 不新增下载器 / 媒体服务器支持

## Done when

- Telegram 运行时已具备最小图片发送或文件发送能力，能把一份明确媒资回到原管理员私聊
- 该能力可被后续渠道接入代码直接复用，不要求先做 personal WeChat
- 现有 Telegram 文本消息、callback、搜索、审批、BT follow-up 不回退
- 现有 Feishu / WeCom 私聊文本能力不回退
- 现有 downloader/import approval 行为不回退
- 现有 metadata / subtitle / refresh 链路不回退

## After this step

按顺序继续：

1. 渠道扩展
   - personal WeChat（默认基于 `wechat-clawbot` Python 包，不采用 npm ClawBot 插件作为主实现形态）
   - Telegram richer card/UI polish
2. 运维清理
   - downloader/library asset correlation and cleanup
