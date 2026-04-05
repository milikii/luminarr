# Current status (v64)

## Project position

Luminarr 当前是一个 **Telegram + personal WeChat + Feishu + WeCom（最小私聊文本基线）** 的垂直影视自动化 Harness。

当前固定主线：
- Telegram + personal WeChat + Feishu + WeCom（当前为最小私聊文本基线）
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
  - Telegram search-result text polish baseline（Telegram 当前会在出口层把共享电影卡片 + 搜索结果文本收紧为更易扫读的标题分区和显式序号提示；personal WeChat / Feishu / WeCom 仍复用 shared private-chat text runtime 原始纯文本）
  - Telegram downloader-approval text polish baseline（Telegram 当前会在出口层把共享下载待确认文本收紧为 `标题 / 选择序号 / 确认命令` 分区；shared `add_to_downloader` 真相文本和其他渠道回复保持不变）
  - Telegram import-approval text polish baseline（Telegram 当前会在出口层把共享导入待确认文本收紧为 `资源 / 任务 ID / 任务 Hash / 确认命令` 分区；shared `import_to_library` 真相文本和其他渠道回复保持不变）
  - personal WeChat login ingress baseline（Telegram 私聊发送 `微信登录` 时，当前进程会调用 `wechat-clawbot` 发起二维码登录；当前把触发该命令的 Telegram 私聊作为回传目标，并回传 SVG 二维码文件；扫码确认成功后会保存 `wechat-clawbot` 凭据并回发最小结果文本）
  - personal WeChat private-chat text baseline（当前进程启动时会读取 `wechat-clawbot` 已保存凭据；若只检测到一个可用账号，则启动最小 `getUpdates -> shared private-chat text runtime -> sendMessage` 文本闭环）
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
  - downloader/library asset correlation baseline（导入成功事件当前会结构化记录下载源路径 + 导入目标路径，且可按 `task_ref / task_id / task_hash` 稳定定位）
  - downloader/library cleanup inspect baseline（当前支持 `cleanup inspect <任务ID或Hash>` / `清理检查 <任务ID或Hash>`；只读返回关联、`source_path / target_path` 是否存在，以及当前 guardrail 是否允许 cleanup）
  - downloader/library cleanup execution baseline（当前支持 `cleanup <任务ID或Hash>` / `清理 <任务ID或Hash>`；会先校验 `source_path + target_path` 关联和 `target_path` 仍存在，再只清理单个 downloader/source 侧已导入资产）
  - downloader/library cleanup command discoverability baseline（当前 bare `cleanup` / `清理` 和 bare `cleanup inspect` / `清理检查` 都会同屏提示“实际清理”与“只读预检”两条用法，帮助用户直接区分执行与预检）
  - downloader/library cleanup rejection follow-up guidance baseline（当前 cleanup 拒绝或失败回复会直接补 `cleanup inspect <任务ID或Hash>` / `清理检查 <任务ID或Hash>` 只读预检提示，并继续显式区分 `cleanup` 的实际清理语义）
  - downloader/library cleanup success follow-up guidance baseline（当前 cleanup 成功回复会直接补 `cleanup inspect <任务ID或Hash>` / `清理检查 <任务ID或Hash>` 只读复核提示，方便用户确认“源已清理、目标保留”）
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
  - 先观察 cleanup inspect + execution + discoverability + rejection guidance + success follow-up 的回归结果；若真实反馈仍显示 inspect 文本衔接不足，再决定是否补最小 inspect-side follow-up，不预先承诺自动化、批量 cleanup 或删种

- **后续体验**
  - 暂无独立条目（Telegram richer card/UI polish 当前已收束）

- **后续运维**
  - 暂无独立条目（当前 next step 已切到 cleanup rejection follow-up guidance）

- **仍未解决的基础能力**
  - real image/media poster rendering
  - multi-process/global locking semantics

## Current risks

- Feishu 当前已接最小 webhook 请求入口、文本回消息和事件验签
- Feishu 当前只支持私聊文本消息 / 文本回复，不支持群聊、图片、卡片、按钮回调
- WeCom 当前已接 callback URL 校验、验签解密入站和最小加密被动文本回包，但仍只支持私聊文本，不支持群聊、图片、卡片、按钮回调或主动发消息 API
- personal WeChat 当前只支持单账号、私聊文本；启动时若检测到多个已保存账号，会显式拒绝启动个人微信文本轮询
- personal WeChat 当前私聊文本轮询在进程启动时读取已保存登录态；同一进程里刚完成 `微信登录` 后，要等下一次启动才会开始监听
- personal WeChat 当前仍不支持群聊、图片、文件、卡片、按钮或多账号编排
- 当前二维码回传落地为 Telegram SVG 文档文件，不是直接 PNG 图片；二维码过期后需要重新发送 `微信登录`
- 当前默认把触发 `微信登录` 的 Telegram 私聊视为管理员二维码回传目标，还没有单独管理员 ACL
- personal WeChat 凭据当前按 `wechat-clawbot` 状态目录规则落盘（`OPENCLAW_STATE_DIR` / `CLAWDBOT_STATE_DIR` / `~/.openclaw`），还没并入项目 SQLite 真相
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
- downloader/library cleanup inspect / execution 当前只对带结构化 `source_path + target_path` 的导入任务可用；更早的历史导入事件若只有旧 `message` 目标路径，inspect / cleanup 都会显式拒绝，仍需人工甄别
- 当前 cleanup inspect / execution / discoverability / rejection guidance / success follow-up 已形成更完整的最小文本闭环，但 inspect 输出本身仍是结果导向文本；若真实回归仍显示衔接不足，再考虑是否只补最小 inspect-side follow-up

## Latest verification

- focused tests: `13 passed` (`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py`)
- focused tests: `3 passed, 64 deselected` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k cleanup`)
- tests: `264 passed, 2 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- manual verification:
  - downloader/library cleanup success follow-up guidance baseline passed（`.venv/bin/python tmp_tests/verify_cleanup_success_follow_up_baseline.py`，脚本随后已删除）
- focused tests: `12 passed` (`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py`)
- focused tests: `3 passed, 64 deselected` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k cleanup`)
- tests: `263 passed, 2 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- manual verification:
  - downloader/library cleanup rejection follow-up guidance baseline passed（`.venv/bin/python tmp_tests/verify_cleanup_rejection_guidance_baseline.py`，脚本随后已删除）
- focused tests: `11 passed` (`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py`)
- focused tests: `3 passed, 64 deselected` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "cleanup"`)
- tests: `262 passed, 2 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- manual verification:
  - downloader/library cleanup command discoverability baseline passed（已运行临时脚本 `tmp_tests/verify_cleanup_command_discoverability.py`，脚本随后已删除）
- focused tests: `79 passed` (`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py tests/test_telegram_bot.py tests/test_execution_policy.py`)
- tests: `262 passed, 2 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- manual verification:
  - downloader/library cleanup inspect baseline passed（`.venv/bin/python tmp_tests/verify_cleanup_inspect_baseline.py`）
- focused tests: `10 passed, 63 deselected` (`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py tests/test_telegram_bot.py -k "cleanup or build_application_registers_services"`)
- focused tests: `126 passed` (`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py tests/test_import_to_library.py tests/test_persistence_sqlite.py tests/test_telegram_bot.py`)
- tests: `257 passed, 2 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- focused tests: `28 passed` (`.venv/bin/python -m pytest -q tests/test_import_to_library.py`)
- focused tests: `25 passed` (`.venv/bin/python -m pytest -q tests/test_persistence_sqlite.py`)
- tests: `248 passed, 2 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- focused tests: `4 passed, 60 deselected` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "import_formats_import_approval_for_telegram or handle_message_import_routes_to_import_service or handle_message_digit_routes_to_add_service or handle_callback_query_digit_routes_to_add_service"`)
- focused tests: `64 passed` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py`)
- tests: `246 passed, 2 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- focused tests: `3 passed, 60 deselected` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "handle_message_digit_routes_to_add_service or handle_callback_query_digit_routes_to_add_service or handle_callback_query_digit_uses_callback_context_when_effective_context_missing"`)
- focused tests: `10 passed` (`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py`)
- focused tests: `63 passed` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py`)
- focused tests: `25 passed, 2 skipped` (`.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py tests/test_feishu_adapter.py tests/test_personal_wechat_text.py tests/test_wecom_adapter.py`)
- tests: `245 passed, 2 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- focused tests: `63 passed` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py`)
- focused tests: `25 passed, 2 skipped` (`.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py tests/test_feishu_adapter.py tests/test_personal_wechat_text.py tests/test_wecom_adapter.py`)
- tests: `245 passed, 2 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- focused tests: `8 passed` (`.venv/bin/python -m pytest -q tests/test_personal_wechat_text.py tests/test_personal_wechat_login.py`)
- focused tests: `1 passed, 62 deselected` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k personal_wechat`)
- focused tests: `91 passed, 2 skipped` (`.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_personal_wechat_login.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py`)
- tests: `245 passed, 2 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
- focused tests: `3 passed` (`.venv/bin/python -m pytest -q tests/test_personal_wechat_login.py`)
- focused tests: `5 passed, 58 deselected` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "personal_wechat_login or telegram_media_sender"`)
- tests: `240 passed, 2 skipped` (`.venv/bin/python -m pytest -q`)
- compile check: `passed` (`python3 -m compileall app tests`)
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
  - downloader/library cleanup execution baseline passed（`.venv/bin/python tmp_tests/verify_cleanup_execution_baseline.py`）
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

- 在已稳定的 Telegram + personal WeChat + Feishu + WeCom 最小私聊文本主链、审批边界和媒体后半段真相之上，先观察已落地 cleanup inspect + execution + discoverability + rejection guidance + success follow-up 的回归结果；若继续推进，也只考虑最小 inspect-side 运维补文，不扩成自动 cleanup、批量运维或删种。
