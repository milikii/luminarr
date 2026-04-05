# Current status (v53)

## Project position

Luminarr 当前是一个 **Telegram + Feishu + WeCom（最小私聊文本基线）** 的垂直影视自动化 Harness。

当前固定主线：
- Telegram + Feishu + WeCom（当前为最小私聊文本基线）
- TMDB
- Prowlarr（当前主来源）+ 最小 BT WebSource（仅 BT 使用）
- Transmission + qBittorrent
- Emby
- SQLite
- Docker Compose
- 单实例 / 单进程 / 单机
- movie-first

## What is implemented now

- **控制层**
  - Telegram runtime
  - Telegram media sending baseline（已能按管理员 `chat_id + 本地路径` 发送图片或文件，并以 `bot_data` 闭包形式供后续二维码/文件回传复用）
  - shared private-chat text runtime baseline（已从 Telegram 收发层抽出可复用文本分发入口）
  - Feishu private-chat identity projection + text event adapter baseline（已能解析最小私聊文本事件，并稳定投影到现有整数 `chat_id/user_id` 边界）
  - Feishu private-chat adapter baseline（最小 webhook 请求入口 + 文本回消息已接上，继续复用 shared private-chat text runtime）
  - Feishu webhook event-signature verification baseline（非 `url_verification` 请求已先验签，再决定是否进入 shared private-chat text runtime）
  - WeCom private-chat decrypted-text adapter kernel baseline（已能解析最小已解密 XML 私聊文本消息，并把 `FromUserName` 稳定投影到现有整数 `chat_id/user_id` 后进入 shared private-chat text runtime）
  - WeCom callback envelope + text reply baseline（已能完成 callback GET URL 校验、POST 验签解密入站，并按最小加密被动文本回包返回到原私聊）
  - `telegram_updates` 去重
  - `jobs` 执行所有权
  - approval / lease / replay guard
  - approval timeout
  - confirm wake context rebuild
  - frustration/reset short-circuit
  - callback routing
  - clarification restart-durable truth
  - read-only concurrency-safe execution policy

- **媒体主链**
  - `search_media`
  - TMDB-first 搜索 + 候选映射持久化
  - downloader approval / `confirm`
  - `status`
  - `import` approval / `confirm`
  - hardlink import
  - cross-filesystem copy-fallback approval
  - completion-monitor
  - post-download auto import（仍保留 `confirm`）
  - filename normalization
  - metadata scraping（TMDB + Fanart.tv）
  - subtitle auto-translation（当前仅 `.srt`）
  - Emby refresh

- **BT 主链**
  - PT / BT parser-level split
  - 原始磁力 processing-path inquiry baseline（`影视入库链 / 纯 BT 下载链`）
  - BT classification（`movie / series / anime / raw_bt`）
  - BT `movie / series / anime` TMDB association
  - `raw_bt` destination selection
  - pure BT single-item ranking baseline（文本型 `下载这个 BT <查询词>` 走最小确定性预过滤 / 优选后进入既有 downloader approval）
  - BT shared source adapter baseline（`Prowlarr + WebSource` 共用候选字段归一化、最小清洗和去重入口）
  - BT external web-source baseline（当前最小站点源为静态 HTML + 直接 magnet / torrent link，且只服务 BT 分流）
  - BT WebSource richer metadata extraction baseline（当前内建 `nyaa` 静态 HTML 已补 `size + seeders`）
  - BT-only read-only helper baseline（`bt搜 <关键词>` / `bt search <关键词>` 复用共享 BT 来源适配，只返回文本候选和调试参考）
  - downloader role binding
  - BT dispatch / transfer execution
  - qBittorrent 最小协议执行（add / status / import-source）
  - BT subscription manual baseline
  - BT subscription scheduler tick baseline
  - BT subscription deterministic candidate-selection baseline

- **其他业务面**
  - `watchlist` 手动持久化基线
  - `watchlist` 的 `movie / series / anime` 分类真相

## What is not implemented yet

- **当前 next step**
  - personal WeChat login ingress baseline（先补最小二维码登录入口，并复用 Telegram 媒资发送回传二维码）

- **后续渠道**
  - personal WeChat

- **后续运维**
  - downloader/library asset correlation and cleanup

- **仍未解决的基础能力**
  - real image/media poster rendering
  - multi-process/global locking semantics

## Current risks

- Feishu 当前已接最小 webhook 请求入口、文本回消息和事件验签
- Feishu 当前只支持私聊文本消息 / 文本回复，不支持群聊、图片、卡片、按钮回调
- WeCom 当前已接 callback URL 校验、验签解密入站和最小加密被动文本回包，但仍只支持私聊文本，不支持群聊、图片、卡片、按钮回调或主动发消息 API
- Telegram 当前已具备最小图片/文件发送闭包，但还没有真实二维码生产者或 personal WeChat 登录入口来触发这条回传链
- personal WeChat 仍未开始登录入口适配
- poster-card 仍然是文本基线
- candidate mapping 仍只保留每个 chat 最近一次搜索窗口
- completion truth 主要依赖 runtime 观察，不是完整独立后台轮询平台
- BT subscription 当前已从“盲拿第一个结果”收紧到共享确定性选源，但仍不是完整质量评分 / 规则引擎
- BT shared source adapter 已接 `Prowlarr + WebSource`，且当前内建 `nyaa` 已补 `size + seeders`；但 richer 字段覆盖和链接校验仍然很薄
- BT-only read-only helper 当前只提供 `bt搜` / `bt search` 最小文本入口，结果只用于人工探索和规则排查，不做候选缓存或后续接力
- 原始磁力入口当前已先问“影视入库链 / 纯 BT 下载链”，但为兼容旧 follow-up，仍接受 `movie/series/anime/raw_bt` 旧回复捷径
- subtitle auto-translation 目前只处理现成 `.srt`，还不支持“从视频里提取英文字幕轨”
- `FANART_API_KEY`、`SUBTITLE_TRANSLATION_API_KEY`、Emby 配置缺失时，相关增强链会失败但不回滚 import success
- pure BT 当前已落地最小确定性单片优选，但仍只覆盖文本型 `下载这个 BT <查询词>`，还不是完整质量评分 / 规则引擎
- `BT_WEB_SOURCES` 当前只做最小来源开关；首批内建站点仍很少，失败时会显式日志提示但不会自动修复站点规则

## Latest verification

- focused tests: `82 passed, 2 skipped` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_private_chat_runtime.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py`)
- tests: `236 passed, 2 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- focused tests: `7 passed, 1 skipped` (`.venv/bin/python -m pytest -q tests/test_wecom_adapter.py`)
- focused tests: `21 passed` (`.venv/bin/python -m pytest -q tests/test_config.py`)
- focused tests: `71 passed, 1 skipped` (`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py`)
- tests: `232 passed, 2 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- focused tests: `4 passed` (`.venv/bin/python -m pytest -q tests/test_wecom_adapter.py`)
- focused tests: `17 passed, 1 skipped` (`.venv/bin/python -m pytest -q tests/test_wecom_adapter.py tests/test_private_chat_runtime.py tests/test_feishu_adapter.py`)
- tests: `226 passed, 1 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- focused tests: `29 passed, 1 skipped` (`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py tests/test_config.py`)
- focused tests: `1 passed, 11 deselected` (`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k feishu_webhook_server_routes_real_http_post_into_shared_runtime`)
- focused tests: `60 passed` (`.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py tests/test_telegram_bot.py`)
- tests: `222 passed, 1 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- focused tests: `28 passed, 1 deselected` (`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py tests/test_feishu_client.py tests/test_config.py -k 'not webhook_server_routes_real_http_post_into_shared_runtime'`)
- focused tests: `1 passed, 8 deselected` (`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py -k webhook_server_routes_real_http_post_into_shared_runtime`)
- focused tests: `60 passed` (`.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py tests/test_telegram_bot.py`)
- tests: `219 passed, 1 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- focused tests: `2 passed` (`.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py`)
- focused tests: `5 passed` (`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py`)
- focused tests: `3 passed, 55 deselected` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "handle_message_replies_search_result or handle_message_magnet_routes_to_bt_direct_split or handle_callback_query_magnet_routes_to_bt_direct_split"`)
- tests: `206 passed` (`.venv/bin/python -m pytest -q`)
- focused tests: `28 passed` (`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py tests/test_manage_bt_subscription.py`)
- focused tests: `79 passed` (`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_telegram_bot.py tests/test_execution_policy.py`)
- focused tests: `23 passed` (`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_manage_bt_subscription.py tests/test_config.py`)
- focused tests: `14 passed` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "bt_processing_path or bt_classification_reply_when_pending or bt_raw_classification_reply_when_pending or bt_tmdb_association_succeeds_for_movie or raw_bt_destination_selection_succeeds or callback_query_magnet_routes_to_bt_direct_split or callback_query_bt_classification_reply_when_pending or callback_query_raw_bt_destination_selection_succeeds or bt_classification_pending_survives_restart or bt_tmdb_association_pending_survives_restart or raw_bt_destination_pending_survives_restart or bt_classification_cancel_when_pending or bt_classification_pending_returns_reminder_for_plain_text"`)
- manual verification:
  - qBittorrent protocol baseline passed
  - BT subscription baseline passed
  - BT subscription scheduler-tick baseline passed
  - BT subscription deterministic candidate-selection baseline passed
  - original magnet processing-path inquiry baseline passed
  - pure BT single-item ranking baseline passed
  - BT external web-source baseline passed
  - BT WebSource richer metadata extraction baseline passed
  - BT-only read-only helper baseline passed

## Current priority

当前只做一件事：

- 在已落地的 Telegram 最小图片/文件发送基线之上，补 personal WeChat 最小二维码登录入口，并直接复用 Telegram 媒资发送把二维码回给管理员私聊；仍然不把这一步扩成 personal WeChat 全量适配或通用媒资平台。
