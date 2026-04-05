# Next step (v59)

## Current baseline

以下能力已经落地，并且本 step 默认全部保持稳定：

- **控制层**
  - Telegram media sending baseline（已能按管理员 `chat_id + 本地路径` 发送图片或文件，并以 `bot_data` 闭包形式供后续二维码/文件回传复用）
  - Telegram search-result text polish baseline（Telegram 当前会在出口层把共享电影卡片 + 搜索结果文本收紧为更易扫读的标题分区和显式序号提示；personal WeChat / Feishu / WeCom 仍复用 shared private-chat text runtime 原始纯文本）
  - Telegram downloader-approval text polish baseline（Telegram 当前会在出口层把共享下载待确认文本收紧为 `标题 / 选择序号 / 确认命令` 分区；shared `add_to_downloader` 真相文本和其他渠道回复保持不变）
  - Telegram import-approval text polish baseline（Telegram 当前会在出口层把共享导入待确认文本收紧为 `资源 / 任务 ID / 任务 Hash / 确认命令` 分区；shared `import_to_library` 真相文本和其他渠道回复保持不变）
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

Continue the next smallest ops-cleanup step by landing a deterministic downloader/library asset-correlation baseline, without automating deletion or changing the landed downloader/import workflow truth boundaries.

## Only do

- 只补 downloader/library asset correlation 的下一小刀，优先把“下载源路径 / 导入目标路径 / 任务引用”之间的最小确定性关联补齐
- 优先复用现有 `task_id / task_hash / task_ref`、`job_event`、导入成功事件和当前 SQLite 持久化真相
- 先做可追溯 correlation 基线，为后续 cleanup 提供依据；当前不直接执行删源、删种或自动清理
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
- 保持现有 personal WeChat / Feishu / WeCom 最小私聊文本链路不变
- 不把这一步扩成通用资产管理平台或通用清理框架

## Do not do

- 不在尚未拿到确定性关联真相前直接删除下载目录内容、种子或库内文件
- 不回头重做 Telegram / personal WeChat / Feishu / WeCom 既有文本链路
- 不改 shared private-chat text runtime 的既有文本协议形状
- 不改现有 downloader / import approval 协议和 `confirm` 边界
- 不改现有 BT shared source adapter、WebSource 规则层、`btsub` 共享选源逻辑
- 不引入通用媒体资产服务、对象存储、CDN 或通用运维平台化
- 不引入 automatic `confirm`
- 不新增下载器 / 媒体服务器支持

## Done when

- 至少一条已导入任务拥有可确定追溯的 downloader source -> library target 关联真相
- 该关联可通过现有 `task_id / task_hash / task_ref` 稳定定位，不依赖自由文本猜测
- 当前 step 不自动删除下载器资产或库内文件
- 现有 Telegram 文本消息、callback、搜索、审批、BT follow-up 不回退
- 已落地的 personal WeChat `微信登录`、私聊文本收发和凭据落盘行为不回退
- 现有 Feishu / WeCom 私聊文本能力不回退
- 现有 downloader/import approval 行为不回退
- 现有 metadata / subtitle / refresh 链路不回退

## After this step

按顺序继续：

1. 运维清理执行
   - 基于已落地 correlation 真相补最小 cleanup 执行和显式保护栏
