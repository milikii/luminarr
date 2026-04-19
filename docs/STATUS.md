# Current status (v312)

## Project position

Luminarr 当前是一个同时服务 **Telegram + personal WeChat + Feishu + WeCom** 四个私聊入口的垂直影视自动化 Harness。

当前固定主线：

- Telegram + personal WeChat + Feishu + WeCom（最小私聊文本基线）
- TMDB
- Prowlarr（当前主来源）+ 最小 BT WebSource（仅 BT 使用）
- Transmission + qBittorrent
- Emby
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
- `docs/JELLYFIN_PLEX_PLAN.md`：当前 Jellyfin / Plex 支持蓝图
- `docs/BT_SCORING_PLAN.md`：刚完成的 BT 共享确定性评分器蓝图
- `docs/BT_SCORING_LOG.md`：刚完成的 BT 共享确定性评分器详细台账
- `docs/QUICK_START_PLAN.md`：刚完成的 quick start 蓝图
- `docs/DEPLOY_CHECKLIST.md`：刚完成的部署者最短路径 checklist
- `docs/SHARED_DELIVERY_UX_LOG.md`：更早完成的“shared private-chat 交付体验收口”详细台账
- `docs/SERIES_ANIME_NAMING_LOG.md`：更早完成的“`series / anime` 独立名称解析最小实现”详细台账
- `docs/APP_MAIN_SLIMMING_LOG.md`：已完成的“`app/main.py` 启动装配 / 下载器路由 helper 瘦身 / 模块化”详细台账
- `docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`：已完成的“`private_chat_runtime.py` shared runtime 编排层瘦身 / 模块化”详细台账
- `docs/CLEANUP_SLIMMING_LOG.md`：已完成的“`cleanup_downloaded_source.py` cleanup 编排层瘦身 / 模块化”详细台账
- `docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`：已完成的“`manage_bt_subscription.py` 订阅编排层瘦身 / 模块化”详细台账
- `docs/SEARCH_MEDIA_SLIMMING_LOG.md`：已完成的“`search_media.py` 搜索编排层瘦身 / 模块化”详细台账
- `docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`：更早完成的“`add_to_downloader.py` 下载编排层瘦身 / 模块化”详细台账
- `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`：更早完成的“`import_to_library.py` 导入编排层瘦身 / 模块化”详细台账
- `docs/TELEGRAM_BOT_SLIMMING_LOG.md`：更早完成的“`telegram_bot.py` 渠道层瘦身 / 模块化”详细台账
- `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`：更早完成的“独立后台下载完成轮询剩余少量回归与验证收口”详细台账
- `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`：已完成的“Feishu 私聊事件解析器去重”详细台账
- `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`：已完成的“Feishu 长连接私有 API 风险收口”详细台账
- `docs/PERSISTENCE_CLOSURE_LOG.md`：更早完成的“持久化吞错收口”详细台账
- `docs/CLEANUP_VERIFICATION_WINDOW.md`：cleanup 已完成窗口的详细证据

## What is implemented now

当前快照按主题归纳；当前主线蓝图统一只看 `docs/BT_SCORING_PLAN.md`，刚完成的部署主线统一只看 `docs/QUICK_START_PLAN.md` 与 `docs/DEPLOY_CHECKLIST.md`，更早完成的 shared delivery / `series-anime` / 各条瘦身与持久化主线继续只看各自台账，状态页不逐天或逐字段追加条目。

- 2026-04-19 已通过 `app/downloader_route_lookup.py` 抽离把 `app/main.py` 主线的下载器路由 helper 收成独立边界；`.venv/bin/python -m pytest -q tests/test_main.py -k "resolve_downloader_name_for_task or resolve_downloader_client_for_lookup or resolve_downloader_client_for_dispatch or get_torrent_status_with_routing or get_torrent_import_source_with_routing"` 得到 `16 passed, 1 deselected`，`app/main.py` 主线满足退出条件 1 并已切到 `series / anime` 解析主线。
- 2026-04-19 已落 `app/services/media_name_parser.py` Phase 1 基线：统一输出 `ParsedMediaName`，覆盖年份、季集、方括号集号、发布组、画质标签、容器和中英混合标题的最小解析；`.venv/bin/python -m pytest -q tests/test_media_name_parser.py` 得到 `10 passed`。
- 2026-04-19 已落 `app/services/naming_rules.yml` 和可选规则加载：parser 现在会把静态噪音词、跨语言别名和质量白名单从规则文件读进来，缺文件或格式错误时回退内置最小集；`.venv/bin/python -m pytest -q tests/test_media_name_parser.py` 得到 `15 passed`。
- 2026-04-19 已把 `series / anime` 主线的最后一个下载完成文件名 fallback 接点 `import_to_library._extract_title_year_for_scrape()` 切到统一 parser；`.venv/bin/python -m pytest -q tests/test_media_name_parser.py tests/test_search_media.py tests/test_import_to_library.py tests/test_get_download_status.py tests/test_subtitle_translator.py` 得到 `245 passed`，该主线满足 `Done when` 第 1 条并已切到 shared private-chat 交付体验主线。
- 2026-04-19 已落 `app/runtime/delivery.py` Phase 1 基线：统一定义 `DeliveryItem` 内容模型和四渠道纯文本 fallback renderer；`.venv/bin/python -m pytest -q tests/test_delivery_renderers.py` 得到 `4 passed`。
- 2026-04-19 已把 `search_media` 成功候选回复接到 shared delivery renderer；`.venv/bin/python -m pytest -q tests/test_delivery_renderers.py tests/test_search_media.py tests/test_private_chat_runtime.py -k "delivery or routes_search or writes_trace_log"` 得到通过，四渠道搜索回复开始按 `channel` 分开展示。
- 2026-04-19 已把 `add_to_downloader` 的待确认下载回复接到 shared delivery renderer；`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py tests/test_private_chat_runtime.py -k "delivery_renderer or add_pending"` 得到通过，四渠道审批提示开始按 `channel` 分层展示。
- 2026-04-19 已把 `get_download_status` 的成功状态回复接到 shared delivery renderer；`.venv/bin/python -m pytest -q tests/test_delivery_renderers.py tests/test_search_media.py tests/test_add_to_downloader.py tests/test_get_download_status.py` 得到通过，shared private-chat 主线满足当前 `Done when` 第 1 条。
- 2026-04-19 已完成 quick start 主线：`docs/DEPLOY_CHECKLIST.md` 覆盖 `Phase 0-6`、`.env.example` 已按分组重构、README §0 已加 checklist 指针；当前唯一主线已切到 BT 共享确定性评分器。
- 2026-04-19 已落 `app/services/bt_candidate_scorer.py` Phase 1 基线：统一 `BTCandidate` / `ScoredCandidate`、标题/链接/去重/低质量/合集预过滤和分辨率/片源/做种数/体积/编码/字幕组打分；`.venv/bin/python -m pytest -q tests/test_bt_candidate_scorer.py` 得到通过。
- 2026-04-19 已落 `app/services/bt_scoring_rules.yml` 和最小 YAML 加载：评分器现在可从仓库规则文件读权重；缺文件或坏字段时打印中文 warning 并回退内置默认值；`.venv/bin/python -m pytest -q tests/test_bt_candidate_scorer.py` 继续通过。
- 2026-04-19 已把 `app/services/pure_bt.py` 的单片优选切到共享评分器，并补 `tests/test_pure_bt.py`；纯 BT 现在复用统一 drop/filter/score 规则，不再自己维护排序分支；`.venv/bin/python -m pytest -q tests/test_bt_candidate_scorer.py tests/test_pure_bt.py` 得到通过。
- 2026-04-19 已把 `app/services/manage_bt_subscription.py::_scan_chat_once()` 的订阅选源切到共享评分器，并补 `tests/test_manage_bt_subscription.py`；订阅扫描现在复用统一低质量过滤、排序和规则文件，但仍保持原有待确认创建、`last_seen` 回写和 scheduler tick 协议不变。
- 2026-04-19 已把 `app/services/search_media.py` 的媒体型 BT 候选展示切到共享评分器排序，并补 `tests/test_search_media.py`；候选展示顺序与 `candidate_mapping` 缓存顺序现在保持一致，BT 评分器主线已满足退出条件 1。
- 2026-04-19 已落 Jellyfin Phase 1 基线：新增 `app/clients/jellyfin.py`、`tests/test_jellyfin_client.py`，并把 `app/main.py` 的媒体服务器 refresh client 创建抽成单独 helper；当前仍保持 Emby 默认路径不变，下一步切到 provider 选择。
- 2026-04-19 已完成 Jellyfin / Plex 主线 Phase 2：`app/config.py` 新增 `MEDIA_SERVER_PROVIDER`、`JELLYFIN_BASE_URL`、`JELLYFIN_API_KEY`，`app/main.py` 已能在 Emby 默认路径之外切到 Jellyfin refresh client；`.venv/bin/python -m pytest -q tests/test_config.py tests/test_main.py tests/test_refresh_media_server.py tests/test_jellyfin_client.py` 得到 `52 passed`，当前最小下一步切到 Plex baseline。
- 2026-04-19 已补 Plex refresh client baseline：新增 `app/clients/plex.py`、`tests/test_plex_client.py`，当前已锁定 Plex refresh URL 和 token 传递方式；`.venv/bin/python -m pytest -q tests/test_plex_client.py tests/test_refresh_media_server.py` 得到 `5 passed`，剩余缺口只剩把 Plex 接进 provider 选择。
- 四个正式私聊入口（Telegram / personal WeChat / Feishu / WeCom）共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相；渠道层只负责验签 / 解密 / 投影 `chat_id / user_id` / 回包。
- 最小可追溯 trace baseline 已落地：shared 入站回包和下载/导入 confirm 关键节点会追加到 `logs/trace.log`，不替代中文故障日志。
- cleanup 完成态、四渠道真实 smoke 证据和窗口 gate 继续只维护在 `docs/CLEANUP_VERIFICATION_WINDOW.md`；当前新主线已切到 Jellyfin / Plex 支持，不回退 cleanup 和 shared delivery 已确认的协议与结论。
- 上一条 BT 订阅主线已把命令解析、媒体类型前缀解析、标题年份抽取和清单增删回复文本抽到 `app/services/bt_subscription_command.py`；扫描候选筛选、`last_seen` 更新和 scheduler tick 继续保留在 service 内，作为已完成主线的剩余结构证据。
- 当前本地联调基线保持 Transmission `http://127.0.0.1:19091`、BT Transmission `http://127.0.0.1:19092`、Emby `http://127.0.0.1:18096`。

## Main risks and gaps

- 当前唯一主线已切到 Jellyfin / Plex 支持；Jellyfin provider 入口和 Plex client baseline 都已落地，最小下一步只剩 Plex 接线。
- 当前风险已从“缺 Plex 协议”收窄到“缺 Plex 装配”：`app/main.py` / `app/config.py` 还没让 `MEDIA_SERVER_PROVIDER=plex` 走到新 client。
- 当前必须继续守住四渠道共用协议、approval、`jobs`、`job_event` 和 SQLite 真相边界，不能在 BT 评分器主线里借机改业务真相。
- cleanup 完成态、四渠道 smoke 证据和 docs gate 仍必须持续稳定；这部分详细证据继续看 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
- `git log --oneline -20` 已包含 `5ad5ba0 Extract downloader route lookup helper`，`app/main.py` 主线完成态已和代码一致。
- quick start 主线已在 2026-04-19 满足 `Done when` 第 1 条；当前唯一主线已先后切到 BT 共享确定性评分器，并已继续切到 Jellyfin / Plex 支持。

## Latest verification

- 窗口活性快照：`jellyfin / plex` 主线已切换
- 当前状态快照：已切换
- 当前结论快照：BT 共享确定性评分器主线已在 2026-04-19 满足退出条件 1；当前唯一主线已切到 Jellyfin / Plex 支持。
- tests：2026-04-14，`858 passed, 2 skipped`（`.venv/bin/python -m pytest -q`）
- 当前主线 focused verification：2026-04-19，`16 passed, 1 deselected`（`.venv/bin/python -m pytest -q tests/test_main.py -k "resolve_downloader_name_for_task or resolve_downloader_client_for_lookup or resolve_downloader_client_for_dispatch or get_torrent_status_with_routing or get_torrent_import_source_with_routing"`）
- 当前主线 focused verification：2026-04-19，`24 passed`（`.venv/bin/python -m pytest -q tests/test_main.py tests/test_refresh_media_server.py tests/test_jellyfin_client.py`）
- 当前主线 focused verification：2026-04-19，`52 passed`（`.venv/bin/python -m pytest -q tests/test_config.py tests/test_main.py tests/test_refresh_media_server.py tests/test_jellyfin_client.py`）
- 当前主线 focused verification：2026-04-19，`5 passed`（`.venv/bin/python -m pytest -q tests/test_plex_client.py tests/test_refresh_media_server.py`）
- 当前主线 focused verification：2026-04-19，`10 passed`（`.venv/bin/python -m pytest -q tests/test_media_name_parser.py`）
- 当前主线 focused verification：2026-04-19，`15 passed`（`.venv/bin/python -m pytest -q tests/test_media_name_parser.py`）
- 当前主线 focused verification：2026-04-19，`184 passed`（`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_bt_sources.py tests/test_import_to_library.py`）
- 刚完成主线 focused verification：2026-04-19，`15 passed`（`.venv/bin/python -m pytest -q tests/test_bt_candidate_scorer.py`）
- 刚完成主线 focused verification：2026-04-19，`5 passed`（`.venv/bin/python -m pytest -q tests/test_pure_bt.py`）
- 刚完成主线 focused verification：2026-04-19，`38 passed`（`.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py`）
- 刚完成主线 focused verification：2026-04-19，`43 passed`（`.venv/bin/python -m pytest -q tests/test_search_media.py`）
- 刚完成主线 focused verification：2026-04-19，`62 passed`（`.venv/bin/python -m pytest -q tests/test_bt_candidate_scorer.py tests/test_pure_bt.py tests/test_manage_bt_subscription.py`）
- 当前主线 focused verification：2026-04-19，`4 passed`（`.venv/bin/python -m pytest -q tests/test_delivery_renderers.py`）
- four-channel cleanup smoke tests：`376 passed`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）
- cleanup service tests：2026-04-19，`46 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py`）
- cleanup focused exit-condition tests：2026-04-19，`18 passed, 28 deselected`（`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py -k "parse_cleanup_query or parse_cleanup_inspect_query or inspect_by_task_ref or resolves_chat_scoped_task_ref"`）
- focused cleanup tests：`526 passed, 93 deselected`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup`）
- cleanup verification docs gate：`384 passed`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`）
- focused config truth tests：`4 passed, 21 deselected`（2026-04-19，`.venv/bin/python -m pytest -q tests/test_config.py -k "requires_token or requires_transmission_base_url or defaults_role_binding_to_first_instance or reads_tmdb_settings"`）
- make run env-file guard tests：`2 passed`（2026-04-13，`.venv/bin/python -m pytest -q tests/test_makefile.py`）
- compile check：2026-04-14，`passed`（`python3 -m compileall app tests`）
- docs consistency check：2026-04-19，`10 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`）
- 上一条主线 focused verification：2026-04-19，`17 passed, 20 deselected`（`.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "parse_bt_subscription_query or add or list or remove or clear"`）
- 上一条主线 focused verification：2026-04-19，`20 passed, 17 deselected`（`.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py -k "run_once or scheduler_tick or last_seen"`）
- 上一条主线 focused verification：2026-04-19，`37 passed`（`.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py`）
- 上一条主线 focused verification：2026-04-19，`12 passed, 27 deselected`（`.venv/bin/python -m pytest -q tests/test_search_media.py -k "parse_movie_query or tmdb or search_and_format_with_results or search_backend_failure"`）
- 上一条主线 focused verification：2026-04-19，`21 passed, 18 deselected`（`.venv/bin/python -m pytest -q tests/test_search_media.py -k "clarification or candidate or quality_from_title"`）
- 上一条主线 focused verification：2026-04-19，`21 passed, 88 deselected`（`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py -k "add_by_selection or add_candidate_source or record_pending_approval or record_pending_job"`）
- 上一条主线 focused verification：2026-04-19，`13 passed, 140 deselected`（`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "handle_callback_query or build_application"`）
- 更早主线 focused verification：2026-04-18，`12 passed, 141 deselected`（`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "pending_list or download_completion_polling or post_download_auto_import_scheduler"`）
- 更早主线真实联调验证：2026-04-18，`passed`（复用 Transmission task_id=`1` task_hash=`e93d696a3e980458765f8016ce39f61437cc9543`；验证其从待轮询列表推进到 `downloader.completed_observed + auto_import boundary`；Emby=`9f4635e04057`）
- 更早主线切换审计：2026-04-18，`15 passed, 34 deselected`（`.venv/bin/python -m pytest -q tests/test_feishu_adapter.py tests/test_feishu_long_connection.py -k "handle_feishu_private_text_event or routes_sdk_event"`）
- 更早主线切换审计：2026-04-18，`passed`（`.venv/bin/python -m pytest -q tests/test_feishu_long_connection.py`；`rg -n "lark_ws_client_module\\.loop|_disconnect|_auto_reconnect|_cache" app/bot/feishu_long_connection.py` 命中 `0`）
- 更早主线切换审计：2026-04-18，`passed`（`bash -lc "git grep -n 'except Exception:\\s*\\(pass\\|return None\\)' app/services app/db app/bot | wc -l"`，命中 `0`）
- 当前主线蓝图：`docs/JELLYFIN_PLEX_PLAN.md`
- 刚完成主线蓝图：`docs/BT_SCORING_PLAN.md`
- 刚完成主线详细台账：`docs/BT_SCORING_LOG.md`
- 刚完成部署主线蓝图：`docs/QUICK_START_PLAN.md`
- 刚完成部署主线交付物：`docs/DEPLOY_CHECKLIST.md`
- 更早主线详细台账：`docs/SHARED_DELIVERY_UX_LOG.md`
- 更早主线详细台账：`docs/SERIES_ANIME_NAMING_LOG.md`
- 上一条主线详细台账：`docs/APP_MAIN_SLIMMING_LOG.md`
- 再上一条主线详细台账：`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`
- 更早主线详细台账：`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`
- 更早主线详细台账：`docs/SEARCH_MEDIA_SLIMMING_LOG.md`
- 更早主线详细台账：`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`
- 更早主线详细台账：`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`
- 更早主线详细台账：`docs/TELEGRAM_BOT_SLIMMING_LOG.md`
- 更早主线详细台账：`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 更早主线详细台账：`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线详细台账：`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线详细台账：`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成详细台账：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- env readiness snapshot：`four-channel cleanup smoke env ready`（2026-04-14，`bash -lc 'source ~/.bashrc >/dev/null 2>&1; python3 -c "import os; keys=[\"TELEGRAM_BOT_TOKEN\",\"PROWLARR_BASE_URL\",\"PROWLARR_API_KEY\",\"TRANSMISSION_BASE_URL\",\"EMBY_BASE_URL\",\"EMBY_API_KEY\",\"FEISHU_APP_ID\",\"FEISHU_APP_SECRET\",\"FEISHU_ENCRYPT_KEY\",\"WECOM_TOKEN\",\"WECOM_ENCODING_AES_KEY\",\"WECOM_RECEIVE_ID\"]; print(\"\\n\".join(f\"{k}=\" + (\"set\" if os.getenv(k,\"\").strip().strip('\"\\'') else \"missing\") for k in keys))"' ; python3 -c "import subprocess; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; rows=dict(line.split('=', 1) for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if '=' in line); lookup={key.lower(): value.strip().strip('\"\\'') for key, value in rows.items()}; print('\\n'.join(f'{k}=' + ('set' if lookup.get(k.lower(), '') else 'missing') for k in keys))" ; python3 -c "from pathlib import Path; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; data={}; env_path=Path('.env'); text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); data.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\\'')) for key, _, value in pairs); print('\\n'.join(f'{k}=' + ('set' if data.get(k, '').strip() else 'missing') for k in keys))"`）
- telegram bot api snapshot：`telegram bot api ready`（2026-04-14，`python3 -c "import json, os, subprocess, urllib.request; from pathlib import Path; token=os.getenv('TELEGRAM_BOT_TOKEN','').strip().strip('\"\\''); env_path=Path('.env'); env_map={}; text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); env_map.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\\'')) for key, _, value in pairs); token=token or env_map.get('TELEGRAM_BOT_TOKEN','').strip(); token=token or next((line.partition('=')[2].strip().strip('\"\\'') for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if line.partition('=')[0].strip().lower() == 'telegram_bot_token'), ''); print('telegram bot token missing' if not token else ('telegram bot api ready' if json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getMe', timeout=5)).get('ok') else 'telegram bot api rejected token'))"`）
- local smoke evidence snapshot：`found in-window cleanup smoke evidence in repo: telegram,personal_wechat,feishu,wecom; all channels covered`（2026-04-14，`sqlite3 -header -column data/luminarr.db "select max(created_at) as max_created_at from jobs; select max(created_at) as max_created_at from job_event; select max(created_at) as max_created_at, count(*) as rows from telegram_updates;" ; rg -n "\[cleanup 私聊 smoke\]" logs`）
- runtime process snapshot：`luminarr process running`（2026-04-14，`python3 -c "from pathlib import Path; proc_root=Path('/proc'); matches=[]; pid_dirs=sorted((path for path in proc_root.iterdir() if path.is_dir() and path.name.isdigit()), key=lambda path: int(path.name)); for pid_dir in pid_dirs:  cmdline_path=pid_dir/'cmdline';  raw=cmdline_path.read_bytes() if cmdline_path.exists() else b'';  tokens=[token.decode('utf-8', errors='ignore') for token in raw.split(b'\\0') if token];  if tokens and 'python' in Path(tokens[0]).name and any(tokens[index] == '-m' and tokens[index + 1] == 'app.main' for index in range(len(tokens) - 1)):   matches.append(f'{pid_dir.name} ' + ' '.join(tokens)); print('luminarr process running' if matches else 'no luminarr process running')"`）
