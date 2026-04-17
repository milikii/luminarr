# Current status (v291)

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

- 当前唯一主线仍是“持久化吞错收口”；cleanup 四渠道验证窗口已完成，shared private-chat runtime 最小抽离已完成。
- Telegram / personal WeChat / Feishu / WeCom 四个正式私聊入口继续共用同一套 shared runtime、approval、`jobs` 和 SQLite 真相。
- 当前也已落一层最小可追溯 trace baseline：shared private-chat 入站/回包，以及下载/导入待确认与 confirm 关键节点会统一追加到 `logs/trace.log`，不替代现有中文故障日志。
- 下载 / 导入待确认与 confirm 主链已经持续收口到 fail-closed：`approval_record` 行缺失、lease/version 读写异常、审批回退失败、成功收尾回写失败，都不会再伪装成普通 not pending 或纯成功。
- 截至 2026-04-17，共享 `approval_repo` 的 approve / cancel / restore 三条审批更新路径里，`approval_record` 缺失行也已从普通状态冲突里拆出单独中文日志与 `[处理建议]`；confirm / cancel 仍保持原来的 fail-closed 文本，不改审批真相和副作用边界。
- 导入 confirm 的历史目标路径查询、审批过期判断也已补齐“结果缺失”和“查询失败”分流；缺失真相时会明确打印中文日志与 `[处理建议]`，不再混成普通“无导入目标路径”或“未过期”。
- 下载 confirm 的审批过期判断现在也已补齐“结果缺失”和“查询失败”分流；缺失真相时会明确打印中文日志与 `[处理建议]`，不再混成普通“未过期”。
- 下载 confirm 的任务抢占阶段现在也已补齐“结果缺失”和“查询失败”分流；缺失真相时会明确打印中文日志与 `[处理建议]`，不再混成普通 lease 更新失败。
- 导入 confirm 的任务抢占阶段现在也已补齐“结果缺失”和“查询失败”分流；缺失真相时会明确打印中文日志与 `[处理建议]`，不再混成普通 lease 更新失败。
- 截至 2026-04-17，最近补齐的最小分流已从下载 / 导入确认链继续扩到下载状态观察落盘：确认任务回退结果缺失、执行版号结果缺失、审批回退结果缺失、取消结果缺失、任务抢占失败，以及下载状态观察空结果 / 缺字段，都已收口成显式中文日志与 `[处理建议]`，但不改 confirm、状态查询、副作用和 SQLite 真相边界；详细条目继续只看 `docs/PERSISTENCE_CLOSURE_LOG.md`。
- 截至 2026-04-17，下载 / 导入确认链的 `jobs` 完结阶段也已补齐“结果缺失”分流：`mark_downloader_completed()` / `mark_completed()` 若返回 `None`，现在会打印显式中文日志与 `[处理建议]`，并在成功回复后继续追加原有 finalization warning，不再把“完结结果缺失”误判成全链已落盘成功。
- 截至 2026-04-17，下载 / 导入确认链的审批更新阶段也已补齐“结果缺失”分流：`approve_downloader()` / `approve_import()` 若返回 `None`，现在会打印显式中文日志与 `[处理建议]`，并让 confirm 直接回状态读取失败，不再把“审批结果缺失”误判成普通 not pending。
- 截至 2026-04-17，下载 / 导入取消链的审批取消阶段也已补齐“结果缺失”分流：`cancel_downloader()` / `cancel_import()` 若返回 `None`，现在会打印显式中文日志与 `[处理建议]`，并让 cancel 直接回状态读取失败，不再把“取消结果缺失”误判成普通状态冲突。
- 截至 2026-04-17，导入入口的 `raw_bt` 判定也已补齐“任务行缺失”分流：`_is_raw_bt_task()` 在 `jobs` 已查不到下载任务行时，会明确打印“导入 raw_bt 判定结果缺失”中文日志并直接 fail-closed，不再把分类真相缺口误判成普通“不是 raw_bt”继续送进入库链。
- 搜索、watchlist、BT 订阅、Telegram BT 待答这些轻状态路径里，写入成功后回读缺失 / 结果缺失 / 条数不一致 已持续收口成显式中文诊断；详细闭环、focused tests 和 commit 轨迹统一只看 `docs/PERSISTENCE_CLOSURE_LOG.md`。
- 截至 2026-04-17，Telegram BT `processing_path` 清理也已补齐“结果缺失”分流：`_clear_bt_processing_path_pending()` / `_pop_bt_processing_path_pending()` 在 `bt_pending_state` 删除直接返回 `None` 时，会明确打印中文日志、放回 in-memory 状态，并让私聊 runtime 直接回服务未就绪，不再把缺失真相混成已取消或已弹出。
- 截至 2026-04-17，Telegram BT `classification` 清理也已补齐“结果缺失”分流：`_clear_bt_classification_pending()` / `_pop_bt_classification_pending()` 在 `bt_pending_state` 删除直接返回 `None` 时，会明确打印中文日志、放回 in-memory 状态，并让私聊 runtime 直接回服务未就绪，不再把缺失真相混成已取消或已弹出。
- 截至 2026-04-17，Telegram BT `tmdb_association` 清理和关联入口也已补齐“结果缺失”分流：`_clear_bt_tmdb_association_pending()` 在 `bt_pending_state` 删除直接返回 `None` 时，会明确打印中文日志、放回 in-memory 状态，并让私聊 runtime 与 TMDB 关联入口直接回服务未就绪，不再把缺失真相混成已取消或继续推进媒体入库链。
- 截至 2026-04-17，Telegram BT `raw_bt_destination` 清理和目录选择入口也已补齐“结果缺失”分流：`_clear_raw_bt_destination_pending()` 在 `bt_pending_state` 删除直接返回 `None` 时，会明确打印中文日志、放回 in-memory 状态，并让私聊 runtime 与目录选择入口直接回服务未就绪，不再把缺失真相混成已取消或继续推进 raw BT 目录选择。
- 截至 2026-04-17，下载待确认轻状态查询 / 取消也已补齐“持久化行缺失”和“SQLite 查询失败”分流：`has_pending_add()` / `confirm_add_by_task_ref()` / `cancel_pending_add()` 在 `jobs` 已查不到待确认任务、但内存里还残留上下文时，会明确打印“下载待确认任务结果缺失”中文日志并直接 fail-closed；而取消链的 `jobs` 查询异常仍保持单独“下载取消查询失败”日志，不再和缺失行混写。
- cleanup 完成态、四渠道真实 smoke 证据和窗口 gate 继续只维护在 `docs/CLEANUP_VERIFICATION_WINDOW.md`，状态页不再回灌长台账。
- 最近提交轨迹继续与当前主线台账同步；详细闭环与验证入口统一收口在 `docs/PERSISTENCE_CLOSURE_LOG.md`。
- 当前本地联调基线保持 Transmission `http://127.0.0.1:19091`、BT Transmission `http://127.0.0.1:19092`、Emby `http://127.0.0.1:18096`。

## Main risks and gaps

- 剩余的持久化吞错缺口仍在其它轻状态和边界路径里；下一步继续按 `docs/NEXT_STEP.md` 逐个最小闭环收口。
- 当前必须继续守住已经落下来的 fail-closed 方向，不能把下载 / 导入 / 搜索 / BT 待答重新放回静默吞错。
- cleanup 完成态、四渠道 smoke 证据和 docs gate 仍必须持续稳定；这部分详细证据继续看 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
- `telegram_bot.py` 已列入后续瘦身任务。
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
- 当前主线 focused verification：详见 `docs/PERSISTENCE_CLOSURE_LOG.md`
- env readiness snapshot：`four-channel cleanup smoke env ready`（2026-04-14，`bash -lc 'source ~/.bashrc >/dev/null 2>&1; python3 -c "import os; keys=[\"TELEGRAM_BOT_TOKEN\",\"PROWLARR_BASE_URL\",\"PROWLARR_API_KEY\",\"TRANSMISSION_BASE_URL\",\"EMBY_BASE_URL\",\"EMBY_API_KEY\",\"FEISHU_APP_ID\",\"FEISHU_APP_SECRET\",\"FEISHU_ENCRYPT_KEY\",\"WECOM_TOKEN\",\"WECOM_ENCODING_AES_KEY\",\"WECOM_RECEIVE_ID\"]; print(\"\\n\".join(f\"{k}=\" + (\"set\" if os.getenv(k,\"\").strip().strip('\"\'') else \"missing\") for k in keys))"' ; python3 -c "import subprocess; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; rows=dict(line.split('=', 1) for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if '=' in line); lookup={key.lower(): value.strip().strip('\"\'') for key, value in rows.items()}; print('\\n'.join(f'{k}=' + ('set' if lookup.get(k.lower(), '') else 'missing') for k in keys))" ; python3 -c "from pathlib import Path; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; data={}; env_path=Path('.env'); text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); data.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\'')) for key, _, value in pairs); print('\\n'.join(f'{k}=' + ('set' if data.get(k, '').strip() else 'missing') for k in keys))"`）
- telegram bot api snapshot：`telegram bot api ready`（2026-04-14，`python3 -c "import json, os, subprocess, urllib.request; from pathlib import Path; token=os.getenv('TELEGRAM_BOT_TOKEN','').strip().strip('\"\''); env_path=Path('.env'); env_map={}; text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); env_map.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\'')) for key, _, value in pairs); token=token or env_map.get('TELEGRAM_BOT_TOKEN','').strip(); token=token or next((line.partition('=')[2].strip().strip('\"\'') for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if line.partition('=')[0].strip().lower() == 'telegram_bot_token'), ''); print('telegram bot token missing' if not token else ('telegram bot api ready' if json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getMe', timeout=5)).get('ok') else 'telegram bot api rejected token'))"`）
- local smoke evidence snapshot：`found in-window cleanup smoke evidence in repo: telegram,personal_wechat,feishu,wecom; all channels covered`（2026-04-14，`sqlite3 -header -column data/luminarr.db "select max(created_at) as max_created_at from jobs; select max(created_at) as max_created_at from job_event; select max(created_at) as max_created_at, count(*) as rows from telegram_updates;" ; rg -n "\[cleanup 私聊 smoke\]" logs`）
- runtime process snapshot：`luminarr process running`（2026-04-14，`python3 -c "from pathlib import Path; proc_root=Path('/proc'); matches=[]; pid_dirs=sorted((path for path in proc_root.iterdir() if path.is_dir() and path.name.isdigit()), key=lambda path: int(path.name)); for pid_dir in pid_dirs:  cmdline_path=pid_dir/'cmdline';  raw=cmdline_path.read_bytes() if cmdline_path.exists() else b'';  tokens=[token.decode('utf-8', errors='ignore') for token in raw.split(b'\\0') if token];  if tokens and 'python' in Path(tokens[0]).name and any(tokens[index] == '-m' and tokens[index + 1] == 'app.main' for index in range(len(tokens) - 1)):   matches.append(f'{pid_dir.name} ' + ' '.join(tokens)); print('luminarr process running' if matches else 'no luminarr process running')"`）
- 当前主线详细台账：`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成详细台账：`docs/CLEANUP_VERIFICATION_WINDOW.md`
