# Current status (v327)

## Project position

Luminarr 当前是一个同时服务 **Telegram + personal WeChat + Feishu + WeCom** 四个私聊入口的垂直影视自动化 Harness。

当前固定主线：

- Telegram + personal WeChat + Feishu + WeCom（最小私聊文本基线）
- TMDB
- Prowlarr（当前主来源）+ 最小 BT WebSource（仅 BT 使用）
- Transmission + qBittorrent
- Emby / Jellyfin / Plex（按配置选择 refresh provider）
- SQLite
- Docker Compose
- 单实例 / 单进程 / 单机
- movie-first

## Knowledge entrypoints

- `README.md`：项目入口
- `docs/INDEX.md`：文档地图
- `docs/GETTING_STARTED.md`：从零到跑通
- `docs/ARCHITECTURE.md`：系统结构说明
- `docs/NEXT_STEP.md`：当前唯一主线
- `docs/STATUS.md`：当前短快照
- `docs/BT_PAGE_RANGE_PLAN.md`：当前 BT allowlist 页面 proof 蓝图
- `docs/JELLYFIN_PLEX_REAL_VERIFICATION_PLAN.md`：刚完成的 Plex 真实 refresh smoke 值得性重评估蓝图
- `docs/JELLYFIN_REAL_VERIFICATION_PLAN.md`：更早完成的 Jellyfin 单 provider 真实 refresh smoke 蓝图
- `docs/JELLYFIN_PLEX_PLAN.md`：当前完成态主线蓝图
- `docs/BT_SCORING_PLAN.md`：刚完成的 BT 共享确定性评分器蓝图
- `docs/BT_SCORING_LOG.md`：刚完成的 BT 共享确定性评分器详细台账
- `docs/QUICK_START_PLAN.md`：刚完成的 quick start 蓝图
- `docs/DEPLOY_CHECKLIST.md`：刚完成的部署者最短路径 checklist
- `docs/SHARED_DELIVERY_UX_LOG.md`：更早完成的 shared private-chat 交付体验收口详细台账
- `docs/SERIES_ANIME_NAMING_LOG.md`：更早完成的 `series / anime` 独立名称解析详细台账
- `docs/APP_MAIN_SLIMMING_LOG.md`：已完成的 `app/main.py` 启动装配 / 下载器路由 helper 瘦身 / 模块化详细台账
- `docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`：已完成的 `private_chat_runtime.py` shared runtime 编排层瘦身 / 模块化详细台账
- `docs/CLEANUP_SLIMMING_LOG.md`：已完成的 `cleanup_downloaded_source.py` cleanup 编排层瘦身 / 模块化详细台账
- `docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`：已完成的 `manage_bt_subscription.py` 订阅编排层瘦身 / 模块化详细台账
- `docs/SEARCH_MEDIA_SLIMMING_LOG.md`：已完成的 `search_media.py` 搜索编排层瘦身 / 模块化详细台账
- `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`：更早完成的 `add_to_downloader.py` 下载编排层瘦身 / 模块化详细台账
- `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`：更早完成的 `import_to_library.py` 导入编排层瘦身 / 模块化详细台账
- `docs/TELEGRAM_BOT_SLIMMING_LOG.md`：更早完成的 `telegram_bot.py` 渠道层瘦身 / 模块化详细台账
- `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`：更早完成的独立后台下载完成轮询收口详细台账
- `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`：更早完成的 Feishu 私聊事件解析器去重详细台账
- `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`：更早完成的 Feishu 长连接私有 API 风险收口详细台账
- `docs/PERSISTENCE_CLOSURE_LOG.md`：更早完成的持久化吞错收口详细台账
- `docs/CLEANUP_VERIFICATION_WINDOW.md`：cleanup 已完成窗口的详细证据

## What is implemented now

- 上一条 BT allowlist 排序显式分页 URL proof 主线已在 2026-04-20 同批次确认满足退出条件；focused tests 已证明 `https://nyaa.si/?s=seeders&o=desc&p=2` 能从命令入口直达页面抓取，并复用现有聊天缓存与 `bt批量确认` 边界，当前 promoted 主线已切到 BT allowlist 搜索排序显式分页 URL proof。
- 更早一条 BT 用户页 / 编号范围页能力主线已在同日冷启动审计中确认满足退出条件，当前继续保持完成态。
- 刚完成的 **Plex 真实 refresh smoke 值得性重评估** 主线保持完成态：当前主机 `http://127.0.0.1:32400/identity` 返回 `000`，本批次不继续追 Plex 实例。
- 再上一条 **Jellyfin / Plex 真实联调重评估** 主线保持完成态：provider 缺配置时的静默关闭 refresh 已收口，focused tests 保持全绿。
- 更早一条 BT 批量任务显式批量确认主线保持完成态：`bt批量 / bt batch` 的确定性批量预览与 `bt批量确认 / bt batch confirm` 的显式批量确认都已完成，focused tests 保持全绿。
- PT live seeding 真相接入 cleanup 阻断这条主线已在冷启动审计里满足文档出口，当前转入完成态；现有 cleanup PT guard 继续保持 `download_monitor.completion_observed_at` 的保守阻断。
- Jellyfin / Plex 支持已基本完成：`app/main.py` 已能按配置选择 Emby / Jellyfin / Plex refresh client；完成态蓝图只看 `docs/JELLYFIN_PLEX_PLAN.md`。
- quick start、BT 共享确定性评分器、shared delivery、`series / anime`、`app/main.py` / `private_chat_runtime.py` / cleanup / BT 订阅 / search / add / import / telegram 渠道层瘦身都保持完成态，不回退成进行中。
- 四个正式私聊入口继续共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相；渠道层只负责验签 / 解密 / 投影 `chat_id / user_id` / 回包。
- 媒体主链继续保持 `search -> downloader approval -> confirm -> dispatch -> status -> import approval -> confirm -> import -> metadata -> subtitle -> refresh`；BT 主链继续保持 PT / BT 分流、processing-path inquiry、共享 BT source adapter、deterministic scorer 与 `btsub` 最小基线。
- cleanup 完成态、四渠道真实 smoke 证据和窗口 gate 继续只维护在 `docs/CLEANUP_VERIFICATION_WINDOW.md`；持久化吞错分流细节继续只维护在 `docs/PERSISTENCE_CLOSURE_LOG.md`。
- 当前完成态入口继续分层：蓝图看 `docs/JELLYFIN_PLEX_PLAN.md`、`docs/BT_SCORING_PLAN.md`、`docs/QUICK_START_PLAN.md`；详细闭环看 `docs/BT_SCORING_LOG.md`、`docs/SHARED_DELIVERY_UX_LOG.md`、`docs/SERIES_ANIME_NAMING_LOG.md`、`docs/APP_MAIN_SLIMMING_LOG.md`、`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`、`docs/CLEANUP_SLIMMING_LOG.md`、`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`、`docs/SEARCH_MEDIA_SLIMMING_LOG.md`、`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`、`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`、`docs/TELEGRAM_BOT_SLIMMING_LOG.md`、`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`、`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`、`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`、`docs/PERSISTENCE_CLOSURE_LOG.md`。

## Main risks and gaps

- 当前仓库正式本地真实 refresh 测试栈仍只有 Emby；Plex 这条线本批次已收口，不再继续追实例。
- BT 当前已经有关键词只读搜索、批量预览和显式批量确认；allowlist 页面 URL 的只读预览、聊天缓存、“页面预览候选复用到 `bt批量确认`”的直接 focused proof、category/list 页面类型，以及 `页面 URL + p=<页码>` 的最小语法糖都已落地。
- 当前最小风险是保持既有页面 URL 只读预览、category/list 页面支持、首页基础页 `https://nyaa.si/`、首页翻页页 `https://nyaa.si/?p=2`、排序列表页 `https://nyaa.si/?s=seeders&o=desc`、排序显式分页组合页 `https://nyaa.si/?s=seeders&o=desc&p=2`、分类基础页 `https://nyaa.si/?c=1_2`、分类搜索基础页 `https://nyaa.si/?f=0&c=1_2&q=frieren`、分类排序组合页 `https://nyaa.si/?c=1_2&s=seeders&o=desc`、分类排序分页组合页 `https://nyaa.si/?c=1_2&s=seeders&o=desc p=2`、分类排序显式分页组合页 `https://nyaa.si/?c=1_2&s=seeders&o=desc&p=2`、用户页基础页 `https://nyaa.si/?u=subsplease`、用户页分页组合页 `https://nyaa.si/?u=subsplease p=2`、用户页显式分页组合页 `https://nyaa.si/?u=subsplease&p=2`、用户页排序组合页 `https://nyaa.si/?u=subsplease&s=seeders&o=desc`、用户页排序分页组合页 `https://nyaa.si/?u=subsplease&s=seeders&o=desc p=2`、带分类用户页显式分页组合页 `https://nyaa.si/?f=0&c=1_2&u=subsplease&p=2`、带分类用户页排序分页组合页 `https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc p=2`、带分类用户页排序显式分页组合页 `https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc&p=2`、搜索页排序组合页 `https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc`、搜索页排序分页组合页 `https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc p=2`、搜索页分页组合页 `https://nyaa.si/?f=0&c=1_2&q=frieren&p=2`、无分类搜索页分页组合页 `https://nyaa.si/?q=frieren&p=2`、无分类搜索基础页 `https://nyaa.si/?q=frieren`、`p=<页码>` 语法和中文拒绝不回退；当前只补搜索排序显式分页 URL proof，不继续扩 allowlist 页面家族。
- Jellyfin / Plex 当前只完成 provider 选择和最小 refresh baseline，不在这一步扩成自动探测或更完整的媒体管理能力。
- cleanup 已完成窗口证据仍成立，`pt_min_seed_hours` 保护也已并入完成态；当前不继续把它扩成 live seeding 秒数新主线。
- 字幕翻译现在已支持 `.srt` + 最小 `.ass`；这一条主线已转入完成态，不再作为当前 promoted 主线。

## Latest verification

- 窗口活性快照：当前主线为 BT allowlist 搜索排序显式分页 URL proof
- 当前状态快照：Plex 这条线已按“当前主机无可达实例”收口；当前真实 refresh 测试栈仍以 Emby 为正式入口。
- 当前结论快照：近 20 条提交与当前完成态记录一致；当前更保守的下一步是补搜索排序显式分页 URL proof，而不是继续追 Plex 或继续扩 allowlist 页面家族。
- BT 排序显式分页 URL focused tests：2026-04-20，`20 passed, 277 deselected`（`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py tests/test_telegram_bot.py -k "sort_page_number_url or sort_page_number or is_supported_web_source_page_url_accepts_nyaa_user_search_list_home_pagination_sort_and_category_sort_pages or resolve_supported_web_source_page_request_appends_page_number"`）
- BT 分类排序显式分页 URL focused tests：2026-04-20，`8 passed, 302 deselected`（`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py tests/test_telegram_bot.py -k "category_sort_page_number_url or category_sort_page_number or is_supported_web_source_page_url_accepts_nyaa_user_search_list_home_pagination_sort_and_category_sort_pages"`）
- BT 带分类用户排序显式分页 URL focused tests：2026-04-20，`6 passed`（bt_sources + search_media + telegram_bot 最小 nodeid 组合）
- BT 无分类用户显式分页 URL focused tests：2026-04-20，`8 passed, 279 deselected`（`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_telegram_bot.py -k "uncategorized_user_page_number_url or uncategorized_user_page_number"`）
- BT 无分类用户排序显式分页 URL focused tests：2026-04-20，`8 passed, 275 deselected`（`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_telegram_bot.py -k "uncategorized_user_sort_page_number_url or uncategorized_user_sort_page_number"`）
- BT 无分类用户排序分页组合页 focused tests：2026-04-20，`10 passed, 280 deselected`（`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py tests/test_telegram_bot.py -k "uncategorized_user_sort_page_number or uncategorized_user_sort_page or is_supported_web_source_page_url_accepts_uncategorized_user_sort_page_number or resolve_supported_web_source_page_request_appends_uncategorized_user_sort_page_number"`）
- BT 无分类用户排序组合页 focused tests：2026-04-20，`5 passed, 279 deselected`（`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py tests/test_telegram_bot.py -k "uncategorized_user_sort_page or is_supported_web_source_page_url_accepts_nyaa_user_search_list_home_pagination_sort_and_category_sort_pages"`）
- BT 首页基础页 focused tests：2026-04-19，`6 passed, 265 deselected`（`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py tests/test_telegram_bot.py -k "home_base_page or is_supported_web_source_page_url_accepts_nyaa_user_search_list_home_pagination_sort_and_category_sort_pages or resolve_supported_web_source_page_request_appends_page_number"`）
- BT 分类搜索基础页 focused tests：2026-04-19，`6 passed, 261 deselected`（`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py tests/test_telegram_bot.py -k "category_search_base_page or is_supported_web_source_page_url_accepts_nyaa_user_search_list_home_pagination_sort_and_category_sort_pages or resolve_supported_web_source_page_request_appends_page_number"`）
- BT 分类基础页 focused tests：2026-04-19，`6 passed, 257 deselected`（`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py tests/test_telegram_bot.py -k "category_base_page or is_supported_web_source_page_url_accepts_nyaa_user_search_list_home_pagination_sort_and_category_sort_pages or resolve_supported_web_source_page_request_appends_page_number"`）
- BT 搜索页排序分页组合页 focused tests：2026-04-19，`6 passed, 242 deselected`（`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py tests/test_telegram_bot.py -k "search_sort_page_number or search_sort_page_number_syntax or search_sort_page_missing_order or resolve_supported_web_source_page_request_appends_page_number"`）
- BT 搜索页分页组合页 focused tests：2026-04-19，`3 passed, 240 deselected`（`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_telegram_bot.py -k "search_page_number or reuses_search_page_number_preview_candidates"`）
- BT 搜索页排序组合页 focused tests：2026-04-19，`5 passed, 239 deselected`（`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py tests/test_telegram_bot.py -k "search_sort_page or is_supported_web_source_page_url_accepts_nyaa_user_search_list_home_pagination_sort_and_category_sort_pages or reuses_search_sort_page_preview_candidates"`）
- BT 用户页排序分页组合页 focused tests：2026-04-19，`5 passed, 235 deselected`（`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py tests/test_telegram_bot.py -k "user_sort_page_number or user_sort_page_number_syntax or resolve_supported_web_source_page_request_appends_page_number"`）
- BT 用户页排序组合页 focused tests：2026-04-19，`6 passed, 230 deselected`（`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py tests/test_telegram_bot.py -k "user_sort_page or resolve_supported_web_source_page_request_appends_page_number or is_supported_web_source_page_url_accepts_nyaa_user_search_list_home_pagination_sort_and_category_sort_pages or reuses_user_sort_page_preview_candidates"`）
- BT 分类排序分页组合页 focused tests：2026-04-19，`5 passed, 227 deselected`（`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py tests/test_telegram_bot.py -k "category_sort_page_number or category_sort_page_number_syntax or category_sort_page_number_syntax_missing_order or resolve_supported_web_source_page_request_appends_page_number"`）
- tests：2026-04-14，`858 passed, 2 skipped`（`.venv/bin/python -m pytest -q`）
- four-channel cleanup smoke tests：2026-04-14，`376 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）
- cleanup service tests：2026-04-19，`49 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py`）
- cleanup PT guard focused tests：2026-04-19，`4 passed, 45 deselected`（`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py -k "pt_seed_window or cleanup_by_task_ref_removes_source_file_and_keeps_target or inspect_by_task_ref_returns_ready_text_without_deleting_source"`）
- focused cleanup tests：2026-04-19，`537 passed, 203 deselected`（`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup`）
- cleanup verification docs gate：2026-04-19，`394 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`）
- focused config truth tests：2026-04-19，`5 passed, 25 deselected`（`.venv/bin/python -m pytest -q tests/test_config.py -k "pt_min_seed_hours or defaults_role_binding_to_first_instance or requires_transmission_base_url or requires_token"`）
- subtitle translator focused tests：2026-04-19，`10 passed`（`.venv/bin/python -m pytest -q tests/test_subtitle_translator.py`）
- import subtitle focused tests：2026-04-19，`2 passed, 140 deselected`（`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k subtitle`）
- make run env-file guard tests：2026-04-13，`2 passed`（`.venv/bin/python -m pytest -q tests/test_makefile.py`）
- compile check：2026-04-14，`passed`（`python3 -m compileall app tests`）
- docs consistency check：2026-04-19，`11 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`）
- focused media-server readiness tests：2026-04-19，`10 passed, 46 deselected`（`.venv/bin/python -m pytest -q tests/test_main.py tests/test_refresh_media_server.py tests/test_config.py -k "media_server or refresh"`）
- focused jellyfin-provider refresh tests：2026-04-19，`9 passed, 17 deselected`（`.venv/bin/python -m pytest -q tests/test_main.py tests/test_refresh_media_server.py -k "refresh"`）
- real jellyfin refresh smoke probe：2026-04-19，`failed with direct target/request_url observability`（一次性临时脚本已执行并删除）
- plex local endpoint probe：2026-04-19，`000`（`curl -sS -o /tmp/plex_probe.out -w "%{http_code}" http://127.0.0.1:32400/identity`）
- BT home pagination focused tests：2026-04-19，`16 passed, 47 deselected`（`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py -k "page or bt_batch"`）
- BT sort page focused tests：2026-04-19，`17 passed, 47 deselected`（`.venv/bin/python -m pytest -q tests/test_bt_sources.py tests/test_search_media.py -k "page or bt_batch"`）
- BT page preview route/cache focused tests：2026-04-19，`5 passed, 203 deselected`（`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_telegram_bot.py -k "bt_batch and page"`）
- BT page preview -> batch confirm focused tests：2026-04-19，`2 passed, 155 deselected`（`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "bt_batch and page"`）
- BT batch preview focused tests：2026-04-19，`9 passed, 200 deselected`（`.venv/bin/python -m pytest -q tests/test_pure_bt.py tests/test_search_media.py tests/test_telegram_bot.py -k "bt_batch or bt_read_only_helper"`）
- BT batch confirm focused tests：2026-04-19，`16 passed, 312 deselected`（`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py tests/test_pure_bt.py tests/test_search_media.py tests/test_telegram_bot.py -k bt_batch`）
- env readiness snapshot：`four-channel cleanup smoke env ready`（2026-04-14，`bash -lc 'source ~/.bashrc >/dev/null 2>&1; python3 -c "import os; keys=[\"TELEGRAM_BOT_TOKEN\",\"PROWLARR_BASE_URL\",\"PROWLARR_API_KEY\",\"TRANSMISSION_BASE_URL\",\"EMBY_BASE_URL\",\"EMBY_API_KEY\",\"FEISHU_APP_ID\",\"FEISHU_APP_SECRET\",\"FEISHU_ENCRYPT_KEY\",\"WECOM_TOKEN\",\"WECOM_ENCODING_AES_KEY\",\"WECOM_RECEIVE_ID\"]; print(\"\\n\".join(f\"{k}=\" + (\"set\" if os.getenv(k,\"\").strip().strip('\"\\'') else \"missing\") for k in keys))"' ; python3 -c "import subprocess; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; rows=dict(line.split('=', 1) for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if '=' in line); lookup={key.lower(): value.strip().strip('\"\\'') for key, value in rows.items()}; print('\\n'.join(f'{k}=' + ('set' if lookup.get(k.lower(), '') else 'missing') for k in keys))" ; python3 -c "from pathlib import Path; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; data={}; env_path=Path('.env'); text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); data.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\\'')) for key, _, value in pairs); print('\\n'.join(f'{k}=' + ('set' if data.get(k, '').strip() else 'missing') for k in keys))"`）
- telegram bot api snapshot：`telegram bot api ready`（2026-04-14，`python3 -c "import json, os, subprocess, urllib.request; from pathlib import Path; token=os.getenv('TELEGRAM_BOT_TOKEN','').strip().strip('\"\\''); env_path=Path('.env'); env_map={}; text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); env_map.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\\'')) for key, _, value in pairs); token=token or env_map.get('TELEGRAM_BOT_TOKEN','').strip(); token=token or next((line.partition('=')[2].strip().strip('\"\\'') for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if line.partition('=')[0].strip().lower() == 'telegram_bot_token'), ''); print('telegram bot token missing' if not token else ('telegram bot api ready' if json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getMe', timeout=5)).get('ok') else 'telegram bot api rejected token'))"`）
- local smoke evidence snapshot：`found in-window cleanup smoke evidence in repo: telegram,personal_wechat,feishu,wecom; all channels covered`（2026-04-14，`sqlite3 -header -column data/luminarr.db "select max(created_at) as max_created_at from jobs; select max(created_at) as max_created_at from job_event; select max(created_at) as max_created_at, count(*) as rows from telegram_updates;" ; rg -n "\[cleanup 私聊 smoke\]" logs`）
- runtime process snapshot：`luminarr process running`（2026-04-14，`python3 -c "from pathlib import Path; proc_root=Path('/proc'); matches=[]; pid_dirs=sorted((path for path in proc_root.iterdir() if path.is_dir() and path.name.isdigit()), key=lambda path: int(path.name)); for pid_dir in pid_dirs: cmdline_path=pid_dir/'cmdline'; raw=cmdline_path.read_bytes() if cmdline_path.exists() else b''; tokens=[token.decode('utf-8', errors='ignore') for token in raw.split(b'\\0') if token]; if tokens and 'python' in Path(tokens[0]).name and any(tokens[index] == '-m' and tokens[index + 1] == 'app.main' for index in range(len(tokens) - 1)): matches.append(f'{pid_dir.name} ' + ' '.join(tokens)); print('luminarr process running' if matches else 'no luminarr process running')"`）
