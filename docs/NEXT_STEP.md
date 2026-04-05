# Next step (v62)

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
  - downloader/library asset correlation baseline（导入成功事件当前会结构化写入 `source_path + target_path`，并可按 `task_ref / task_id / task_hash` 稳定定位）
  - downloader/library cleanup inspect baseline（当前支持 `cleanup inspect <任务ID或Hash>` / `清理检查 <任务ID或Hash>`；只读返回关联、路径存在性和当前 guardrail 结果）
  - downloader/library cleanup execution baseline（当前支持 `cleanup <任务ID或Hash>` / `清理 <任务ID或Hash>`；会先校验 `source_path + target_path` 关联和 `target_path` 仍存在，再只清理单个 downloader/source 侧已导入资产）
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

Continue the next smallest ops-cleanup step by landing a deterministic downloader/library cleanup-command discoverability baseline, on top of the landed cleanup-inspect + cleanup-execution truth, so the user can more clearly tell apart "只读预检" and "实际清理" from the command help text itself, without turning it into cleanup automation or changing the landed downloader/import workflow truth boundaries.

## Only do

- 只补 cleanup 命令家族的最小 discoverability 文本，不新增新的 cleanup 副作用
- 明确区分两条已落地路径：
  - `cleanup <任务ID或Hash>` / `清理 <任务ID或Hash>`：实际清理下载源资产
  - `cleanup inspect <任务ID或Hash>` / `清理检查 <任务ID或Hash>`：只读预检，不删除任何文件
- 优先复用现有 `cleanup` parser、service 和当前 SQLite 真相边界，不引入新的 cleanup workflow
- 保持现有 inspect / execution 真相和 guardrail 判定不变
- 保持现有自然语言 / 文本协议形状不变：
  - `search/select/status/import/confirm/cleanup/watchlist/btsub`
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

- 不改已落地 cleanup inspect / execution 的判断逻辑、guardrail 条件或删除范围
- 不让 inspect 直接删除任何下载源资产、库内目标、sidecar 或其他任务文件
- 不在未校验 correlation 真相和 `target_path` 存在前放宽现有 cleanup execution 保护栏
- 不删除 library target、metadata sidecar、subtitle sidecar 或其他任务资产
- 不做后台自动 cleanup、scheduler 批量扫描或通用清理平台化
- 不回头重做 Telegram / personal WeChat / Feishu / WeCom 既有文本链路
- 不改 shared private-chat text runtime 的既有文本协议形状
- 不改现有 downloader / import approval 协议和 `confirm` 边界
- 不改现有 BT shared source adapter、WebSource 规则层、`btsub` 共享选源逻辑
- 不引入通用媒体资产服务、对象存储、CDN 或通用运维平台化
- 不引入 automatic `confirm`
- 不新增下载器 / 媒体服务器支持

## Done when

- bare `cleanup` / `清理` 或 cleanup inspect 用法提示，能让用户在不看文档时也看出“执行”和“只读预检”的区别
- 不新增新的 cleanup 命令家族、自动化路径或批量入口
- 已落地 cleanup inspect / execution 的输出、保护栏和删除范围不回退
- 当前 step 不扩成自动删除下载器资产、删种、库内文件清理平台或批量运维入口
- 已落地的 cleanup execution baseline 行为和保护栏不回退
- 现有 Telegram 文本消息、callback、搜索、审批、BT follow-up 不回退
- 已落地的 personal WeChat `微信登录`、私聊文本收发和凭据落盘行为不回退
- 现有 Feishu / WeCom 私聊文本能力不回退
- 现有 downloader/import approval 行为不回退
- 现有 metadata / subtitle / refresh 链路不回退

## After this step

按顺序继续：

1. 视最小 cleanup inspect + execution 的保护栏和回归结果，再决定是否继续扩到更连续的运维动作；当前仍不预先承诺自动化、批量 cleanup 或删种
