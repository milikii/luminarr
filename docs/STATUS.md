# Current status (v313)

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

- 当前进行中的 promoted 主线是 PT live seeding 真相接入 cleanup 阻断；目标是在不放宽 fail-closed 的前提下，把 downloader 当前做种真相接到 `pt_min_seed_hours` 判断。
- 当 `PT_MIN_SEED_HOURS` > 0 时，PT 任务的 `cleanup inspect` / `cleanup` 已会按 `download_monitor.completion_observed_at` 做保守时间窗阻断；缺少必要真相时显式拒绝。
- Jellyfin / Plex 支持已基本完成：`app/main.py` 已能按配置选择 Emby / Jellyfin / Plex refresh client；完成态蓝图只看 `docs/JELLYFIN_PLEX_PLAN.md`。
- quick start、BT 共享确定性评分器、shared delivery、`series / anime`、`app/main.py` / `private_chat_runtime.py` / cleanup / BT 订阅 / search / add / import / telegram 渠道层瘦身都保持完成态，不回退成进行中。
- 四个正式私聊入口继续共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相；渠道层只负责验签 / 解密 / 投影 `chat_id / user_id` / 回包。
- 媒体主链继续保持 `search -> downloader approval -> confirm -> dispatch -> status -> import approval -> confirm -> import -> metadata -> subtitle -> refresh`；BT 主链继续保持 PT / BT 分流、processing-path inquiry、共享 BT source adapter、deterministic scorer 与 `btsub` 最小基线。
- cleanup 完成态、四渠道真实 smoke 证据和窗口 gate 继续只维护在 `docs/CLEANUP_VERIFICATION_WINDOW.md`；持久化吞错分流细节继续只维护在 `docs/PERSISTENCE_CLOSURE_LOG.md`。
- 当前完成态入口继续分层：蓝图看 `docs/JELLYFIN_PLEX_PLAN.md`、`docs/BT_SCORING_PLAN.md`、`docs/QUICK_START_PLAN.md`；详细闭环看 `docs/BT_SCORING_LOG.md`、`docs/SHARED_DELIVERY_UX_LOG.md`、`docs/SERIES_ANIME_NAMING_LOG.md`、`docs/APP_MAIN_SLIMMING_LOG.md`、`docs/PRIVATE_CHAT_RUNTIME_SLIMMING_LOG.md`、`docs/CLEANUP_SLIMMING_LOG.md`、`docs/MANAGE_BT_SUBSCRIPTION_SLIMMING_LOG.md`、`docs/SEARCH_MEDIA_SLIMMING_LOG.md`、`docs/ADD_TO_DOWNLOADER_SLIMMING_LOG.md`、`docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`、`docs/TELEGRAM_BOT_SLIMMING_LOG.md`、`docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`、`docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`、`docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`、`docs/PERSISTENCE_CLOSURE_LOG.md`。

## Main risks and gaps

- 当前 PT live seeding 主线刚提升完成，代码尚未补齐；后续施工必须守住“优先读 live seeding 真相，拿不到就继续 fail-closed”边界。
- cleanup PT 最小保护窗口这一步只基于 `download_monitor.completion_observed_at` 做保守阻断；还不是 downloader live seeding 秒数能力。
- Jellyfin / Plex 当前只完成 provider 选择和最小 refresh baseline，不在这一步扩成自动探测或更完整的媒体管理能力。
- cleanup 已完成窗口证据仍成立，`pt_min_seed_hours` 保护也已并入完成态；但这还不是 downloader live seeding 秒数能力。
- 字幕翻译现在已支持 `.srt` + 最小 `.ass`；这一条主线已转入完成态，不再作为当前 promoted 主线。

## Latest verification

- 窗口活性快照：当前主线为 PT live seeding 真相接入 cleanup 阻断
- 当前状态快照：`.ass` 字幕最小支持已通过 focused tests 收口，并已切到 PT live seeding 真相主线。
- 当前结论快照：近 20 条提交与当前完成态记录一致；`.ass` 字幕 focused tests 已通过，下一步优先补 downloader live seeding 真相而不是继续放大字幕能力边界。
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
- env readiness snapshot：`four-channel cleanup smoke env ready`（2026-04-14，`bash -lc 'source ~/.bashrc >/dev/null 2>&1; python3 -c "import os; keys=[\"TELEGRAM_BOT_TOKEN\",\"PROWLARR_BASE_URL\",\"PROWLARR_API_KEY\",\"TRANSMISSION_BASE_URL\",\"EMBY_BASE_URL\",\"EMBY_API_KEY\",\"FEISHU_APP_ID\",\"FEISHU_APP_SECRET\",\"FEISHU_ENCRYPT_KEY\",\"WECOM_TOKEN\",\"WECOM_ENCODING_AES_KEY\",\"WECOM_RECEIVE_ID\"]; print(\"\\n\".join(f\"{k}=\" + (\"set\" if os.getenv(k,\"\").strip().strip('\"\\'') else \"missing\") for k in keys))"' ; python3 -c "import subprocess; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; rows=dict(line.split('=', 1) for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if '=' in line); lookup={key.lower(): value.strip().strip('\"\\'') for key, value in rows.items()}; print('\\n'.join(f'{k}=' + ('set' if lookup.get(k.lower(), '') else 'missing') for k in keys))" ; python3 -c "from pathlib import Path; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; data={}; env_path=Path('.env'); text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); data.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\\'')) for key, _, value in pairs); print('\\n'.join(f'{k}=' + ('set' if data.get(k, '').strip() else 'missing') for k in keys))"`）
- telegram bot api snapshot：`telegram bot api ready`（2026-04-14，`python3 -c "import json, os, subprocess, urllib.request; from pathlib import Path; token=os.getenv('TELEGRAM_BOT_TOKEN','').strip().strip('\"\\''); env_path=Path('.env'); env_map={}; text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); env_map.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\\'')) for key, _, value in pairs); token=token or env_map.get('TELEGRAM_BOT_TOKEN','').strip(); token=token or next((line.partition('=')[2].strip().strip('\"\\'') for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if line.partition('=')[0].strip().lower() == 'telegram_bot_token'), ''); print('telegram bot token missing' if not token else ('telegram bot api ready' if json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getMe', timeout=5)).get('ok') else 'telegram bot api rejected token'))"`）
- local smoke evidence snapshot：`found in-window cleanup smoke evidence in repo: telegram,personal_wechat,feishu,wecom; all channels covered`（2026-04-14，`sqlite3 -header -column data/luminarr.db "select max(created_at) as max_created_at from jobs; select max(created_at) as max_created_at from job_event; select max(created_at) as max_created_at, count(*) as rows from telegram_updates;" ; rg -n "\[cleanup 私聊 smoke\]" logs`）
- runtime process snapshot：`luminarr process running`（2026-04-14，`python3 -c "from pathlib import Path; proc_root=Path('/proc'); matches=[]; pid_dirs=sorted((path for path in proc_root.iterdir() if path.is_dir() and path.name.isdigit()), key=lambda path: int(path.name)); for pid_dir in pid_dirs: cmdline_path=pid_dir/'cmdline'; raw=cmdline_path.read_bytes() if cmdline_path.exists() else b''; tokens=[token.decode('utf-8', errors='ignore') for token in raw.split(b'\\0') if token]; if tokens and 'python' in Path(tokens[0]).name and any(tokens[index] == '-m' and tokens[index + 1] == 'app.main' for index in range(len(tokens) - 1)): matches.append(f'{pid_dir.name} ' + ' '.join(tokens)); print('luminarr process running' if matches else 'no luminarr process running')"`）
