# Next step (v55)

## Current baseline

以下能力已经落地，并且本 step 默认全部保持稳定：

- **控制层**
  - Telegram media sending baseline（已能按管理员 `chat_id + 本地路径` 发送图片或文件，并以 `bot_data` 闭包形式供后续二维码/文件回传复用）
  - personal WeChat login ingress baseline（Telegram 私聊发送 `微信登录` 时，当前进程会调用 `wechat-clawbot` 发起二维码登录；当前把触发该命令的 Telegram 私聊作为回传目标，并以 SVG 文档文件形式回传二维码；扫码确认成功后会回最小结果文本并保存 `wechat-clawbot` 凭据）
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

Continue the smallest personal WeChat private-chat text step by reusing the landed QR login credentials and shared private-chat text runtime.

## Only do

- 只补 personal WeChat 最小私聊文本收发
- 继续复用已落地的 `微信登录` 二维码入口和 `wechat-clawbot` 凭据落盘，不重做登录入口
- 默认基于 `wechat-clawbot` Python 包已有的凭据、长轮询 `getUpdates`、`sendMessage` 能力，不采用 npm ClawBot 插件作为主实现形态
- 目标只服务“已登录 -> personal WeChat 私聊文本入站 -> shared private-chat text runtime -> 文本回消息”这一条最小闭环
- 继续复用当前 Telegram runtime、Application、shared private-chat text runtime，以及现有 Telegram `微信登录` 入口
- 保持现有自然语言 / 文本协议形状不变：
  - `微信登录`
  - `search/select/status/import/confirm/watchlist/btsub`
  - `bt搜 <关键词>` / `bt search <关键词>`
- 保持 shared private-chat text runtime 的文本分发边界不变
- personal WeChat 外部会话标识 / 用户标识继续先做带渠道命名空间的整数投影，再进入现有 `chat_id/user_id` 边界
- 保持现有 workflow 和 service 真相边界不变：
  - `search_media`
  - `add_to_downloader`
  - `get_download_status`
  - `import_to_library`
  - `manage_watchlist`
  - `manage_bt_subscription`
- 继续复用现有 downloader / import approval 边界
- 继续复用现有 BT 分流、原始磁力 processing-path inquiry、pure BT、`btsub`、BT-only read-only helper
- 只补“加载已保存登录态 -> 收到 private text -> 文本回消息”这条最小链路

## Do not do

- 不重做 personal WeChat 二维码登录入口、二维码图片栈或凭据协议
- 不补群聊、频道、图片、文件、语音、卡片、按钮、内联富交互
- 不把这一步扩成 Telegram 卡片 UI overhaul
- 不改 shared private-chat text runtime 的既有文本协议形状
- 不改现有 SQLite / approval / jobs / lease 真相协议
- 不改现有 downloader / import approval 协议
- 不改现有 BT shared source adapter、WebSource 规则层、`btsub` 共享选源逻辑
- 不改现有原始磁力处理链问询形状
- 不引入通用多渠道媒资抽象层
- 不引入通用文件资产服务、对象存储或 CDN
- 不做多账号 personal WeChat 编排
- 不把 `wechat-clawbot` 凭据并入当前 SQLite
- 不引入 automatic `confirm`
- 不新增下载器 / 媒体服务器支持

## Done when

- 当前进程已能读取 `wechat-clawbot` 已保存的 personal WeChat 登录凭据并启动最小私聊文本收发
- personal WeChat 私聊文本入站已能投影到现有整数 `chat_id/user_id` 后进入 shared private-chat text runtime
- runtime 产出的最小文本回复已能回到原 personal WeChat 私聊
- 已落地的 Telegram `微信登录` 二维码入口和凭据落盘行为不回退
- 现有 Telegram 文本消息、callback、搜索、审批、BT follow-up 不回退
- 现有 Feishu / WeCom 私聊文本能力不回退
- 现有 downloader/import approval 行为不回退
- 现有 metadata / subtitle / refresh 链路不回退

## After this step

按顺序继续：

1. 渠道体验
   - Telegram richer card/UI polish
2. 运维清理
   - downloader/library asset correlation and cleanup
