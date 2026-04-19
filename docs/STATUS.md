# Current status (v307)

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
- `docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`：当前“`private_chat_runtime.py` shared runtime 编排层瘦身 / 模块化”详细台账
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

当前快照按主题归纳；当前主线具体路径、focused tests 和风险分组统一只看 `docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`，上一条主线详细闭环继续只看 `docs/CLEANUP_SLIMMING_LOG.md`，更早主线继续只看 `docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`、`docs/SEARCH_MEDIA_SLIMMING_LOG.md`、`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`、`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`、`docs/TELEGRAM_BOT_SLIMMING_LOG.md`、`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`、`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`、`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md` 和 `docs/PERSISTENCE_CLOSURE_LOG.md`，状态页不逐天或逐字段追加条目。

- `private_chat_runtime.py` shared runtime 编排层瘦身主线已在 2026-04-19 通过 `_log_private_chat_inbound()` / `_wrap_reply_with_trace()` helper 抽离 + focused tests 满足 `Done when` 第 2 条；按 `docs/NEXT_STEP.md` 应切到 `After this step` 第 1 项 `app/main.py` 启动装配 / 下载器路由 helper 瘦身 / 模块化。
- 四个正式私聊入口（Telegram / personal WeChat / Feishu / WeCom）共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相；渠道层只负责验签 / 解密 / 投影 `chat_id / user_id` / 回包。
- 最小可追溯 trace baseline 已落地：shared 入站回包和下载/导入 confirm 关键节点会追加到 `logs/trace.log`，不替代中文故障日志。
- cleanup 完成态、四渠道真实 smoke 证据和窗口 gate 继续只维护在 `docs/CLEANUP_VERIFICATION_WINDOW.md`；当前新主线只做 shared runtime 编排层瘦身，不回退 cleanup 已确认的协议和 guardrail。
- 上一条 BT 订阅主线已把命令解析、媒体类型前缀解析、标题年份抽取和清单增删回复文本抽到 `app/services/bt_subscription_command.py`；扫描候选筛选、`last_seen` 更新和 scheduler tick 继续保留在 service 内，作为已完成主线的剩余结构证据。
- 当前本地联调基线保持 Transmission `http://127.0.0.1:19091`、BT Transmission `http://127.0.0.1:19092`、Emby `http://127.0.0.1:18096`。

## Main risks and gaps

- `private_chat_runtime.py` shared runtime 编排层瘦身已达到可测量退出条件；剩余 pending gate / 命令分发内联分支不再继续拆零碎小口，下一步直接切到 `app/main.py` 主线。
- 当前必须继续守住已经落下来的 fail-closed 方向，不能在做 `private_chat_runtime.py` 瘦身时回退四渠道共用协议、approval、`jobs`、`job_event` 和 SQLite 真相边界。
- cleanup 完成态、四渠道 smoke 证据和 docs gate 仍必须持续稳定；这部分详细证据继续看 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
- `git log --oneline -20` 近 20 条提交标题仍主要停在 `manage_bt_subscription` 完成态和后续规划文档，尚未单独命名 cleanup/runtime 主线切换；冷启动时应以 `docs/NEXT_STEP.md`、当前代码树和 focused tests 为准。
- `private_chat_runtime.py`、`app/main.py` 已列入当前主线与后续编排层瘦身计划；`cleanup_downloaded_source.py` 已转入已完成主线台账。
- `series / anime` 名称解析、`.ass` 字幕支持仍是更后面的工作，不提前并行展开。

## Latest verification

- 窗口活性快照：runtime 主线已完成，待切到下一条主线
- 当前状态快照：待切换
- 当前结论快照：`private_chat_runtime.py` shared runtime 编排层瘦身主线已在 2026-04-19 通过 `_log_private_chat_inbound()` / `_wrap_reply_with_trace()` helper 抽离 + focused tests 满足退出条件 2；下一步按 `docs/NEXT_STEP.md` 切到 `After this step` 第 1 项 `app/main.py`。
- tests：2026-04-14，`858 passed, 2 skipped`（`.venv/bin/python -m pytest -q`）
- 当前主线 focused verification：2026-04-19，`34 passed, 17 deselected`（`.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py -k "routes_search_without_telegram_update or routes_bt_prompt_without_telegram_update or routes_cleanup or routes_bare_cleanup or personal_wechat_login or writes_trace_log or replies_service_not_ready"`）
- four-channel cleanup smoke tests：`376 passed`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）
- cleanup service tests：2026-04-19，`46 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py`）
- cleanup focused exit-condition tests：2026-04-19，`18 passed, 28 deselected`（`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py -k "parse_cleanup_query or parse_cleanup_inspect_query or inspect_by_task_ref or resolves_chat_scoped_task_ref"`）
- focused cleanup tests：`526 passed, 93 deselected`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup`）
- cleanup verification docs gate：`384 passed`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`）
- focused config truth tests：`4 passed, 21 deselected`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_config.py -k "requires_token or requires_transmission_base_url or defaults_role_binding_to_first_instance or reads_tmdb_settings"`）
- make run env-file guard tests：`2 passed`（2026-04-13，`.venv/bin/python -m pytest -q tests/test_makefile.py`）
- compile check：2026-04-14，`passed`（`python3 -m compileall app tests`）
- docs consistency check：2026-04-19，`9 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`）
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
- 当前主线详细台账：`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`
- 上一条主线详细台账：`docs/CLEANUP_SLIMMING_LOG.md`
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
