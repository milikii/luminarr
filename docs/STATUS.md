# Current status (v301)

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
- `docs/PERSISTENCE_CLOSURE_LOG.md`：当前“持久化吞错收口”详细台账
- `docs/CLEANUP_VERIFICATION_WINDOW.md`：cleanup 已完成窗口的详细证据

## What is implemented now

当前快照按主题归纳；所有具体路径、focused tests 和 commit 轨迹统一只看 `docs/PERSISTENCE_CLOSURE_LOG.md`，状态页不逐天或逐字段追加条目。

- 当前唯一主线仍是“持久化吞错收口”；cleanup 四渠道验证窗口已完成，shared private-chat runtime 最小抽离已完成。
- 四个正式私聊入口（Telegram / personal WeChat / Feishu / WeCom）共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相；渠道层只负责验签 / 解密 / 投影 `chat_id / user_id` / 回包。
- 最小可追溯 trace baseline 已落地：shared 入站回包和下载/导入 confirm 关键节点会追加到 `logs/trace.log`，不替代中文故障日志。
- 下载 / 导入 confirm 主链已经全链 fail-closed：待确认创建、过期判断、任务抢占、审批回退 / 取消、成功收尾与执行版号回写，三类真相缺口（“结果缺失”“记录损坏”“SQLite 异常”）各自拆出独立中文日志与 `[处理建议]`，不再伪装成 not pending 或纯成功。
- 共享 `approval_repo` 的 approve / cancel / restore 三路也已把 `approval_record` 缺失行从普通状态冲突里拆开；confirm / cancel 的用户侧文本和副作用边界保持不变。
- 事件落盘链（`job_event.append_event()`：下载 / 导入 / cleanup / 状态观察 / 下载完成观察）全部补齐“结果缺失”“写后回读命中坏行”两路分流，均保持原来的后续 workflow 边界，不改副作用。
- 下载监控 / 状态观察（`download_monitor.register_download()` / `record_status()`）、后台完成轮询待轮询列表、自动导入候选与终态查询、自动导入跳过事件，均已收口“空结果 / 写后回读缺失 / 记录损坏”三类分流，本轮观察或自动导入按原有 warning 或停路边界处理。
- 轻状态路径（`search` 待澄清与候选、`watchlist`、`BT 订阅` 与扫描、Telegram BT 待答四态）里的写入-回读-清单读取-删除-清空-最近资源回写，都已把“真缺数据 / 回读缺失 / 命中坏行 / SQLite 异常”拆开；用户侧失败文本和 `SERVICE_NOT_READY_TEXT` 边界不变。
- 导入 confirm 的上下文重建、历史目标路径查询、命名真相读取、`raw_bt` 判定，以及下载 confirm 的上下文重建，都已补齐“任务行 / 事件行记录损坏”分流，confirm 统一按状态读取失败 fail-closed，不继续送坏记录进入库或下载链。
- cleanup 完成态、四渠道真实 smoke 证据和窗口 gate 继续只维护在 `docs/CLEANUP_VERIFICATION_WINDOW.md`；最近提交轨迹与当前主线详细闭环继续只看 `docs/PERSISTENCE_CLOSURE_LOG.md`。
- 当前本地联调基线保持 Transmission `http://127.0.0.1:19091`、BT Transmission `http://127.0.0.1:19092`、Emby `http://127.0.0.1:18096`。

## Main risks and gaps

- 剩余的持久化吞错缺口仍在其它轻状态和边界路径里；下一步继续按 `docs/NEXT_STEP.md` 逐个最小闭环收口。
- 当前必须继续守住已经落下来的 fail-closed 方向，不能把下载 / 导入 / 搜索 / BT 待答重新放回静默吞错。
- cleanup 完成态、四渠道 smoke 证据和 docs gate 仍必须持续稳定；这部分详细证据继续看 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
- `telegram_bot.py`、`import_to_library.py`、`add_to_downloader.py`、`search_media.py`、`manage_bt_subscription.py`、`private_chat_runtime.py`、`app/main.py` 已列入当前主线后的编排层瘦身计划。
- Feishu 长连接私有 API 风险、`series / anime` 名称解析、`.ass` 字幕支持仍是当前主线之后的工作，不提前并行展开。

## Latest verification

- 窗口活性快照：已满足退出条件
- 当前状态快照：已完成
- 当前结论快照：验证窗口已满足退出条件；截至 2026-04-14，Telegram / personal WeChat / Feishu / WeCom 四个渠道真实私聊 cleanup smoke 与其余退出证据已全部满足，窗口正式完成。
- tests：2026-04-14，`858 passed, 2 skipped`（`.venv/bin/python -m pytest -q`）
- four-channel cleanup smoke tests：`376 passed`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）
- cleanup service tests：2026-04-14，`38 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py`）
- focused cleanup tests：`526 passed, 93 deselected`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup`）
- cleanup verification docs gate：`384 passed`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`）
- focused config truth tests：`4 passed, 21 deselected`（2026-04-14，`.venv/bin/python -m pytest -q tests/test_config.py -k "requires_token or requires_transmission_base_url or defaults_role_binding_to_first_instance or reads_tmdb_settings"`）
- make run env-file guard tests：`2 passed`（2026-04-13，`.venv/bin/python -m pytest -q tests/test_makefile.py`）
- compile check：2026-04-14，`passed`（`python3 -m compileall app tests`）
- docs consistency check：2026-04-17，`passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`）
- 当前主线 focused verification：2026-04-18，`2 passed, 131 deselected`（`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "context_lookup or context_row_corruption"`）
- 当前主线 focused verification：2026-04-18，`3 passed, 129 deselected`（`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "naming_truth"`）
- 当前主线 focused verification：2026-04-18，`8 passed, 123 deselected`（`.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "raw_bt"`）
- 当前主线 focused verification：2026-04-18，`6 passed, 147 deselected`（`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "dedup_result_missing or dedup_persist_fails or update_id_invalid or callback_id_missing"`）
- 当前主线 focused verification：2026-04-18，`3 passed, 148 deselected`（`.venv/bin/python -m pytest -q tests/test_telegram_bot.py -k "pending_list"`）
- 当前主线 focused verification：详见 `docs/PERSISTENCE_CLOSURE_LOG.md`
- env readiness snapshot：`four-channel cleanup smoke env ready`（2026-04-14，`bash -lc 'source ~/.bashrc >/dev/null 2>&1; python3 -c "import os; keys=[\"TELEGRAM_BOT_TOKEN\",\"PROWLARR_BASE_URL\",\"PROWLARR_API_KEY\",\"TRANSMISSION_BASE_URL\",\"EMBY_BASE_URL\",\"EMBY_API_KEY\",\"FEISHU_APP_ID\",\"FEISHU_APP_SECRET\",\"FEISHU_ENCRYPT_KEY\",\"WECOM_TOKEN\",\"WECOM_ENCODING_AES_KEY\",\"WECOM_RECEIVE_ID\"]; print(\"\\n\".join(f\"{k}=\" + (\"set\" if os.getenv(k,\"\").strip().strip('\"\'') else \"missing\") for k in keys))"' ; python3 -c "import subprocess; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; rows=dict(line.split('=', 1) for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if '=' in line); lookup={key.lower(): value.strip().strip('\"\'') for key, value in rows.items()}; print('\\n'.join(f'{k}=' + ('set' if lookup.get(k.lower(), '') else 'missing') for k in keys))" ; python3 -c "from pathlib import Path; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; data={}; env_path=Path('.env'); text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); data.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\'')) for key, _, value in pairs); print('\\n'.join(f'{k}=' + ('set' if data.get(k, '').strip() else 'missing') for k in keys))"`）
- telegram bot api snapshot：`telegram bot api ready`（2026-04-14，`python3 -c "import json, os, subprocess, urllib.request; from pathlib import Path; token=os.getenv('TELEGRAM_BOT_TOKEN','').strip().strip('\"\''); env_path=Path('.env'); env_map={}; text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); env_map.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\'')) for key, _, value in pairs); token=token or env_map.get('TELEGRAM_BOT_TOKEN','').strip(); token=token or next((line.partition('=')[2].strip().strip('\"\'') for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if line.partition('=')[0].strip().lower() == 'telegram_bot_token'), ''); print('telegram bot token missing' if not token else ('telegram bot api ready' if json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getMe', timeout=5)).get('ok') else 'telegram bot api rejected token'))"`）
- local smoke evidence snapshot：`found in-window cleanup smoke evidence in repo: telegram,personal_wechat,feishu,wecom; all channels covered`（2026-04-14，`sqlite3 -header -column data/luminarr.db "select max(created_at) as max_created_at from jobs; select max(created_at) as max_created_at from job_event; select max(created_at) as max_created_at, count(*) as rows from telegram_updates;" ; rg -n "\[cleanup 私聊 smoke\]" logs`）
- runtime process snapshot：`luminarr process running`（2026-04-14，`python3 -c "from pathlib import Path; proc_root=Path('/proc'); matches=[]; pid_dirs=sorted((path for path in proc_root.iterdir() if path.is_dir() and path.name.isdigit()), key=lambda path: int(path.name)); for pid_dir in pid_dirs:  cmdline_path=pid_dir/'cmdline';  raw=cmdline_path.read_bytes() if cmdline_path.exists() else b'';  tokens=[token.decode('utf-8', errors='ignore') for token in raw.split(b'\\0') if token];  if tokens and 'python' in Path(tokens[0]).name and any(tokens[index] == '-m' and tokens[index + 1] == 'app.main' for index in range(len(tokens) - 1)):   matches.append(f'{pid_dir.name} ' + ' '.join(tokens)); print('luminarr process running' if matches else 'no luminarr process running')"`）
- 当前主线详细台账：`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成详细台账：`docs/CLEANUP_VERIFICATION_WINDOW.md`
