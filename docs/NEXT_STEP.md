# Next step (v56)

## Current baseline

以下能力已经落地，并且本 step 默认全部保持稳定：

- **控制层**
  - Telegram media sending baseline（已能按管理员 `chat_id + 本地路径` 发送图片或文件，并以 `bot_data` 闭包形式供后续二维码/文件回传复用）
  - personal WeChat login ingress baseline（Telegram 私聊发送 `微信登录` 时，当前进程会调用 `wechat-clawbot` 发起二维码登录；当前把触发该命令的 Telegram 私聊作为回传目标，并以 SVG 文档文件形式回传二维码；扫码确认成功后会回最小结果文本并保存 `wechat-clawbot` 凭据）
  - personal WeChat private-chat text baseline（当前进程启动时会读取 `wechat-clawbot` 已保存凭据；若只检测到一个可用账号，则启动最小 `getUpdates -> shared private-chat text runtime -> sendMessage` 文本闭环）
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

Continue the smallest Telegram richer card/UI polish step without changing the landed multi-channel text runtime or workflow truth boundaries.

## Only do

- 只补 Telegram richer card/UI polish 的最小一刀，优先收紧 Telegram 搜索/选择阶段的消息排版和可扫读性
- 继续复用当前 Telegram runtime、现有 callback/文本协议，以及 shared private-chat text runtime
- 保持现有自然语言 / 文本协议形状不变：
  - `search/select/status/import/confirm/watchlist/btsub`
  - `bt搜 <关键词>` / `bt search <关键词>`
  - `微信登录`
- 保持现有 workflow 和 service 真相边界不变：
  - `search_media`
  - `add_to_downloader`
  - `get_download_status`
  - `import_to_library`
  - `manage_watchlist`
  - `manage_bt_subscription`
- 保持现有 approval / jobs / lease / SQLite 协议不变
- 保持现有 personal WeChat / Feishu / WeCom 最小私聊文本链路不变
- 当前这一步只处理 Telegram 展示层，不把它扩成通用富交互平台

## Do not do

- 不回头重做 personal WeChat 二维码登录、凭据协议或私聊文本适配
- 不改 shared private-chat text runtime 的既有文本协议形状
- 不改现有 SQLite / approval / jobs / lease 真相协议
- 不改现有 downloader / import approval 协议
- 不改现有 BT shared source adapter、WebSource 规则层、`btsub` 共享选源逻辑
- 不改现有原始磁力处理链问询形状
- 不引入 poster 渲染、通用媒体资产服务、对象存储或 CDN
- 不把这一步扩成群聊、图片、文件、卡片按钮或通用多渠道平台化
- 不引入 automatic `confirm`
- 不新增下载器 / 媒体服务器支持

## Done when

- Telegram 搜索/选择阶段至少有一处高频消息已收紧为更易扫读的 richer 展示，而不改其业务含义
- 现有 Telegram 文本消息、callback、搜索、审批、BT follow-up 不回退
- 已落地的 personal WeChat `微信登录`、私聊文本收发和凭据落盘行为不回退
- 现有 Feishu / WeCom 私聊文本能力不回退
- 现有 downloader/import approval 行为不回退
- 现有 metadata / subtitle / refresh 链路不回退

## After this step

按顺序继续：

1. 运维清理
   - downloader/library asset correlation and cleanup
