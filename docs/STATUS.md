# Current status (v270)

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
- 下载和导入待确认链已经收口到 fail-closed：`approval_record` 查询异常、审批行缺失、lease/version 读写异常，不再混成普通 not pending。
- 下载 confirm 的异常回退链也已补一处 fail-closed：下载投递失败后，如果待确认审批回退失败，不再继续回普通下载失败，而会直接按状态不可用停路。
- 下载 confirm 的成功收尾链也已补 warning：下载已真实投递后，如果 `approval_record/jobs` 回写失败，回复会显式提示不要重复 `confirm`，不再伪装成纯成功。
- 导入 confirm 的异常回退链也已补一处 fail-closed：导入执行失败或进入 copy-fallback 待确认后，如果待确认审批回退失败，不再继续回普通执行结果，而会直接按状态不可用停路。
- 导入 confirm 的成功收尾链也已补 warning：导入已成功后，如果 `approval_record/jobs` 回写失败，回复会显式提示不要重复 `confirm`，不再伪装成纯成功。
- Telegram BT 待答状态也已补一处 fail-closed：BT processing/classification/tmdb/raw-destination 写库失败时，不再继续发下一步提示，而会回 `SERVICE_NOT_READY_TEXT`。
- Telegram BT `processing_path` 清理链也已补一处 fail-closed：清理失败时不再把旧状态当成“已取消”或“已弹出”，而会保留内存态并回 `SERVICE_NOT_READY_TEXT`。
- Telegram BT `classification` 清理链也已补一处 fail-closed：清理失败时不再把旧状态当成“已取消”或“已弹出”，而会保留内存态并回 `SERVICE_NOT_READY_TEXT`。
- Telegram BT `tmdb_association` 清理链也已补一处 fail-closed：清理失败时不再把旧 TMDB 关联态当成“已取消”或继续推进后续媒体入库链，而会保留内存态并回 `SERVICE_NOT_READY_TEXT`。
- Telegram BT `raw_bt_destination` 清理链也已补一处 fail-closed：清理失败时不再把旧目录选择当成“已取消”或继续推进后续链路，而会保留内存态并回 `SERVICE_NOT_READY_TEXT`。
- 搜索链最近几轮也已收口到 fail-closed：待澄清写入失败、旧澄清态清理失败、候选缓存写入失败，都不再保留误导性的 in-memory 状态。
- 自动导入低质量资源的规则跳过链也已补一处 fail-closed：`job_event` 跳过事件写入失败时，不再继续回“已跳过自动导入”，而会按状态不可用停路，避免把持久化缺口混成普通规则命中。
- BT 订阅最近资源回写链已补一处分流：订阅条目已不存在时，不再和 SQLite 回写异常共用同一类 warning；现在会显式提示“待确认已创建，但订阅条目已不存在”。
- BT 订阅最近资源回写链继续补一处分流：回写返回空结果时，不再和普通 SQLite 回写异常共用同一类日志，而会单独提示“BT 订阅最近资源回写结果缺失”；但用户侧仍保持原来的 warning，不改 `btsub run` 副作用边界。
- BT 订阅写入入口也已补一处分流：插入查询直接返回空结果时，不再和普通 SQLite 查询异常共用同一类日志，而会单独提示“BT 订阅写入结果缺失”；但用户侧仍保持原来的失败文本。
- 想看写入入口也已补一处分流：插入返回空结果时，不再和普通 SQLite 写入异常共用同一类日志，而会单独提示“想看写入结果缺失”；但用户侧仍保持原来的失败文本。
- 想看清单写入链也已补一处分流：新增后回读不到条目时，会打印“写入后条目缺失”日志，不再和普通 SQLite 写入失败共用同一类诊断。
- BT 订阅写入链也已补一处分流：新增后回读不到条目时，会打印“BT 订阅写入后条目缺失”日志，不再和普通 SQLite 写入失败共用同一类诊断。
- 搜索待澄清写入链也已补一处分流：写入后立即回读不到记录时，会打印“搜索澄清态写入后记录缺失”日志，不再和普通 SQLite 写入失败共用同一类诊断。
- 搜索澄清态清理链也已补一处分流：删除返回空结果时，不再和普通 SQLite 删除异常共用同一类日志，而会单独提示“搜索澄清态清理结果缺失”；但 fail-closed 行为保持不变，当前进程会恢复待澄清内存态。
- Telegram BT 待答写入链也已补一处分流：`bt_pending_state` 写入后立即回读不到记录时，会打印“BT 待处理写入后记录缺失”日志，不再和普通 SQLite 写入失败共用同一类诊断。
- 搜索候选写入链也已补一处分流：`candidate_mapping` 保存后条数和预期不一致时，会打印“搜索候选写入后记录不一致”日志，不再和普通 SQLite 写入失败共用同一类诊断。
- 截至 2026-04-17，当前主线最近 5 个最小闭环已经继续收口到“写入成功但回读缺失 / 条数不一致”的分流诊断：想看清单、BT 订阅、搜索待澄清、Telegram BT 待答、搜索候选这几条轻状态路径，都已补成显式中文日志与 `[处理建议]`，详细 focused tests 和 commit 轨迹继续只记在 `docs/PERSISTENCE_CLOSURE_LOG.md`。
- 下载状态观察链也已补一处分流：`download_monitor` 返回空 update、缺回读记录、或缺完成标记时，不再都只打印同一类观察落盘失败日志，而会分别提示“结果缺失 / 完成标记缺失”与对应 `[处理建议]`，但用户侧仍保持原来的状态 warning，不改自动导入 follow-up 边界。
- 导入命名真相读取链也已补一处分流：`job_event` 查询直接返回空结果时，不再和普通 SQLite 查询异常共用同一类日志，而会单独提示“导入命名真相结果缺失”；但导入命名仍保持原来的 fallback，不改导入副作用边界。
- 自动导入终态读取链也已补一处分流：`job_event` 查询直接返回空结果时，不再和普通 SQLite 查询异常共用同一类日志，而会单独提示“自动导入终态结果缺失”；但自动导入仍保持原来的 fail-closed 停路边界。
- 自动导入扫描入口也已补一处分流：`download_monitor` 已完成列表查询直接返回空结果时，不再和普通 SQLite 查询异常共用同一类日志，而会单独提示“自动导入候选结果缺失”；但本轮自动导入仍保持原来的 fail-closed 停路边界。
- `btsub run` 扫描入口也已补一处分流：订阅列表查询直接返回空结果时，不再和普通 SQLite 查询异常共用同一类日志，而会单独提示“BT 订阅扫描结果缺失”；但本轮扫描仍保持原来的 fail-closed 停路边界。
- `btsub` scheduler tick 起点也已补一处分流：chat 列表查询直接返回空结果时，不再和普通 SQLite 查询异常共用同一类日志，而会单独提示“BT 订阅扫描 chat 列表结果缺失”；但 tick 仍保持原来的 fail-closed 停路边界。
- `watchlist list` 读取链也已补一处分流：清单查询直接返回空结果时，不再和普通 SQLite 查询异常共用同一类日志，而会单独提示“想看清单结果缺失”；但用户侧仍保持原来的失败文本。
- `watchlist remove` 删除链也已补一处分流：删除查询直接返回空结果时，不再和普通 SQLite 查询异常共用同一类日志，而会单独提示“想看删除结果缺失”；但用户侧仍保持原来的失败文本。
- `watchlist clear` 清空链也已补一处分流：清空查询直接返回空结果时，不再和普通 SQLite 查询异常共用同一类日志，而会单独提示“想看清单清空结果缺失”；但用户侧仍保持原来的失败文本。
- `btsub list` 读取链也已补一处分流：订阅清单查询直接返回空结果时，不再和普通 SQLite 查询异常共用同一类日志，而会单独提示“BT 订阅清单结果缺失”；但用户侧仍保持原来的失败文本。
- `btsub remove` 删除链也已补一处分流：删除查询直接返回空结果时，不再和普通 SQLite 查询异常共用同一类日志，而会单独提示“BT 订阅删除结果缺失”；但用户侧仍保持原来的失败文本。
- `btsub clear` 清空链也已补一处分流：清空查询直接返回空结果时，不再和普通 SQLite 查询异常共用同一类日志，而会单独提示“BT 订阅清单清空结果缺失”；但用户侧仍保持原来的失败文本。
- cleanup 详细门禁、真实私聊 smoke 证据和窗口快照继续只写在 `docs/CLEANUP_VERIFICATION_WINDOW.md`，不再回灌到状态页长台账。
- 当前本地联调基线仍是 Transmission `http://127.0.0.1:19091`、BT Transmission `http://127.0.0.1:19092`、Emby `http://127.0.0.1:18096`。
- `docs/STATUS.md` 从本版开始只保留短快照；当前主线的详细闭环、focused tests 和 commit 轨迹收口到 `docs/PERSISTENCE_CLOSURE_LOG.md`。

## Main risks and gaps

- 剩余的持久化吞错缺口仍在其它轻状态和边界路径里；下一步继续按 `docs/NEXT_STEP.md` 逐个最小闭环收口。
- `docs/NEXT_STEP.md` 仍然偏长，但当前最大 token 放大器已经从状态页拆走；后续如果继续瘦身，优先继续压缩 NEXT_STEP 的长 guard 列表。
- cleanup 完成态、四渠道 smoke 证据和 docs gate 仍必须持续稳定；这部分详细证据继续看 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
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
- docs consistency check：2026-04-14，`passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`）
- env readiness snapshot：`four-channel cleanup smoke env ready`（2026-04-14，`bash -lc 'source ~/.bashrc >/dev/null 2>&1; python3 -c "import os; keys=[\"TELEGRAM_BOT_TOKEN\",\"PROWLARR_BASE_URL\",\"PROWLARR_API_KEY\",\"TRANSMISSION_BASE_URL\",\"EMBY_BASE_URL\",\"EMBY_API_KEY\",\"FEISHU_APP_ID\",\"FEISHU_APP_SECRET\",\"FEISHU_ENCRYPT_KEY\",\"WECOM_TOKEN\",\"WECOM_ENCODING_AES_KEY\",\"WECOM_RECEIVE_ID\"]; print(\"\\n\".join(f\"{k}=\" + (\"set\" if os.getenv(k,\"\").strip().strip('\"\'') else \"missing\") for k in keys))"' ; python3 -c "import subprocess; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; rows=dict(line.split('=', 1) for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if '=' in line); lookup={key.lower(): value.strip().strip('\"\'') for key, value in rows.items()}; print('\\n'.join(f'{k}=' + ('set' if lookup.get(k.lower(), '') else 'missing') for k in keys))" ; python3 -c "from pathlib import Path; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; data={}; env_path=Path('.env'); text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); data.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\'')) for key, _, value in pairs); print('\\n'.join(f'{k}=' + ('set' if data.get(k, '').strip() else 'missing') for k in keys))"`）
- telegram bot api snapshot：`telegram bot api ready`（2026-04-14，`python3 -c "import json, os, subprocess, urllib.request; from pathlib import Path; token=os.getenv('TELEGRAM_BOT_TOKEN','').strip().strip('\"\''); env_path=Path('.env'); env_map={}; text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); env_map.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\'')) for key, _, value in pairs); token=token or env_map.get('TELEGRAM_BOT_TOKEN','').strip(); token=token or next((line.partition('=')[2].strip().strip('\"\'') for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if line.partition('=')[0].strip().lower() == 'telegram_bot_token'), ''); print('telegram bot token missing' if not token else ('telegram bot api ready' if json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getMe', timeout=5)).get('ok') else 'telegram bot api rejected token'))"`）
- local smoke evidence snapshot：`found in-window cleanup smoke evidence in repo: telegram,personal_wechat,feishu,wecom; all channels covered`（2026-04-14，`sqlite3 -header -column data/luminarr.db "select max(created_at) as max_created_at from jobs; select max(created_at) as max_created_at from job_event; select max(created_at) as max_created_at, count(*) as rows from telegram_updates;" ; rg -n "\[cleanup 私聊 smoke\]" logs`）
- runtime process snapshot：`luminarr process running`（2026-04-14，`python3 -c "from pathlib import Path; proc_root=Path('/proc'); matches=[]; pid_dirs=sorted((path for path in proc_root.iterdir() if path.is_dir() and path.name.isdigit()), key=lambda path: int(path.name)); for pid_dir in pid_dirs:  cmdline_path=pid_dir/'cmdline';  raw=cmdline_path.read_bytes() if cmdline_path.exists() else b'';  tokens=[token.decode('utf-8', errors='ignore') for token in raw.split(b'\\0') if token];  if tokens and 'python' in Path(tokens[0]).name and any(tokens[index] == '-m' and tokens[index + 1] == 'app.main' for index in range(len(tokens) - 1)):   matches.append(f'{pid_dir.name} ' + ' '.join(tokens)); print('luminarr process running' if matches else 'no luminarr process running')"`）
- 当前主线详细台账：`docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 已完成详细台账：`docs/CLEANUP_VERIFICATION_WINDOW.md`
