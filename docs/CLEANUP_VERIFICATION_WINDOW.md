# Cleanup verification window (2026-04-05 to 2026-04-12) (v48)

## Window

- 当前状态：已完成
- 开始日期：2026-04-05
- 最早可结束日期：2026-04-12
- 窗口活性：已满足退出条件
- 聚合 smoke gate：`tests/test_cleanup_cross_channel_smoke.py`
- 当前目标：四个渠道都至少完成 1 次真实私聊 cleanup smoke，确认“消息进来 -> shared runtime -> 文本回去”不回退。
- 当前结论：验证窗口已满足退出条件；截至 2026-04-14，Telegram / personal WeChat / Feishu / WeCom 四个渠道真实私聊 cleanup smoke 与其余退出证据已全部满足，窗口正式完成。

## Exit checklist

- [x] 完成 2026-04-05 到 2026-04-12 的真实使用验证窗口
- [x] Telegram 完成至少 1 次真实私聊 cleanup smoke
- [x] personal WeChat 完成至少 1 次真实私聊 cleanup smoke
- [x] Feishu 完成至少 1 次真实私聊 cleanup smoke
- [x] WeCom 完成至少 1 次真实私聊 cleanup smoke
- [x] `tests/test_cleanup_cross_channel_smoke.py` 持续通过
- [x] cleanup discoverability / inspect / execution / rejection guidance / success follow-up / failure observability 没有协议回退
- [x] verification docs gate 持续通过

## Channel progress

| 渠道 | 状态 | 最近一次日期 | 备注 |
| --- | --- | --- | --- |
| Telegram | 已完成 | 2026-04-14 | 2026-04-14 已完成真实私聊 smoke |
| personal WeChat | 已完成 | 2026-04-14 | 2026-04-14 已完成真实私聊 smoke |
| Feishu | 已完成 | 2026-04-14 | 2026-04-14 已完成真实私聊 smoke |
| WeCom | 已完成 | 2026-04-14 | 2026-04-14 已完成真实私聊 smoke |

## Verification evidence

- 最近一次聚合 smoke gate：2026-04-14，`376 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）
- 最近一次 cleanup 协议回归验证：2026-04-14，`526 passed, 93 deselected`（`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup`）
- 最近一次 verification docs gate：2026-04-14，`384 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`）
- 当前环境就绪快照：2026-04-14，`four-channel cleanup smoke env ready`（`bash -lc 'source ~/.bashrc >/dev/null 2>&1; python3 -c "import os; keys=[\"TELEGRAM_BOT_TOKEN\",\"PROWLARR_BASE_URL\",\"PROWLARR_API_KEY\",\"TRANSMISSION_BASE_URL\",\"EMBY_BASE_URL\",\"EMBY_API_KEY\",\"FEISHU_APP_ID\",\"FEISHU_APP_SECRET\",\"FEISHU_ENCRYPT_KEY\",\"WECOM_TOKEN\",\"WECOM_ENCODING_AES_KEY\",\"WECOM_RECEIVE_ID\"]; print(\"\\n\".join(f\"{k}=\" + (\"set\" if os.getenv(k,\"\").strip().strip('\"\'') else \"missing\") for k in keys))"' ; python3 -c "import subprocess; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; rows=dict(line.split('=', 1) for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if '=' in line); lookup={key.lower(): value.strip().strip('\"\'') for key, value in rows.items()}; print('\\n'.join(f'{k}=' + ('set' if lookup.get(k.lower(), '') else 'missing') for k in keys))" ; python3 -c "from pathlib import Path; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY','TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; data={}; env_path=Path('.env'); text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); data.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\'')) for key, _, value in pairs); print('\\n'.join(f'{k}=' + ('set' if data.get(k, '').strip() else 'missing') for k in keys))"`）
- 当前 Telegram Bot API 就绪快照：2026-04-14，`telegram bot api ready`（`python3 -c "import json, os, subprocess, urllib.request; from pathlib import Path; token=os.getenv('TELEGRAM_BOT_TOKEN','').strip().strip('\"\''); env_path=Path('.env'); env_map={}; text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; lines=(line.strip() for line in text.splitlines()); pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); env_map.update(((key.removeprefix('export ').strip()), value.strip().strip('\"\'')) for key, _, value in pairs); token=token or env_map.get('TELEGRAM_BOT_TOKEN','').strip(); token=token or next((line.partition('=')[2].strip().strip('\"\'') for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if line.partition('=')[0].strip().lower() == 'telegram_bot_token'), ''); print('telegram bot token missing' if not token else ('telegram bot api ready' if json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getMe', timeout=5)).get('ok') else 'telegram bot api rejected token'))"`）
- 当前仓库证据快照：2026-04-14，`found in-window cleanup smoke evidence in repo: telegram,personal_wechat,feishu,wecom; all channels covered`（`sqlite3 -header -column data/luminarr.db "select max(created_at) as max_created_at from jobs; select max(created_at) as max_created_at from job_event; select max(created_at) as max_created_at, count(*) as rows from telegram_updates;" ; rg -n "\[cleanup 私聊 smoke\]" logs`）
- 当前运行进程快照：2026-04-14，`luminarr process running`（`python3 -c "from pathlib import Path; proc_root=Path('/proc'); matches=[]; pid_dirs=sorted((path for path in proc_root.iterdir() if path.is_dir() and path.name.isdigit()), key=lambda path: int(path.name)); for pid_dir in pid_dirs:  cmdline_path=pid_dir/'cmdline';  raw=cmdline_path.read_bytes() if cmdline_path.exists() else b'';  tokens=[token.decode('utf-8', errors='ignore') for token in raw.split(b'\\0') if token];  if tokens and 'python' in Path(tokens[0]).name and any(tokens[index] == '-m' and tokens[index + 1] == 'app.main' for index in range(len(tokens) - 1)):   matches.append(f'{pid_dir.name} ' + ' '.join(tokens)); print('luminarr process running' if matches else 'no luminarr process running')"`）
- 当前 cleanup 协议观察：截至 2026-04-14，cleanup discoverability / inspect / mixed-case english cleanup protocol / correlation-missing unresolved-identity blank display / target-missing cleanup inspect follow-up guidance / source-missing cleanup inspect follow-up guidance / cleanup inspect follow-up guidance / guard-rejected cleanup inspect follow-up guidance / post-cleanup cleanup inspect confirmation / chat-scoped task_ref post-cleanup cleanup inspect confirmation / chat-scoped task_ref correlation-missing inspect identity resolution / chat-scoped task_ref correlation-missing rejection guidance / chat-scoped task_ref correlation-query-failure observability / chat-scoped task_ref correlation-query-failure identity retention / chat-scoped task_ref missing-structured-import-correlation identity retention / chat-scoped task_ref delete-failure observability / chat-scoped task_ref success-event-append-failure observability / chat-scoped task_ref source-type-unsupported blocked-log observability / cleanup-service-not-ready fix-hint observability / chat-scoped task_ref target-missing cleanup inspect follow-up guidance / chat-scoped task_ref source-missing cleanup inspect follow-up guidance / chat-scoped task_ref source-type-unsupported cleanup inspect follow-up guidance / chat-scoped task_ref guard-rejected cleanup inspect follow-up guidance / chat-scoped task_ref target-missing rejection guidance / chat-scoped task_ref source-missing rejection guidance / chat-scoped task_ref source-type-unsupported rejection guidance / chat-scoped task_ref guard-rejected rejection guidance / execution / correlation-missing / target-missing / source-missing / source-type-unsupported / guard-rejected rejection guidance / success follow-up / failure observability 未见协议回退。

## PT 做种 guardrail 评估

- 评估日期：2026-04-07
- 已核对代码入口：`app/services/cleanup_downloaded_source.py::_inspect_cleanup`、`app/services/cleanup_downloaded_source.py::_validate_cleanup_paths`
- 当前 cleanup guardrail 是否读取下载器做种状态：未覆盖；现有 guardrail 只检查 import 关联、`source_path/target_path` 是否存在、源类型是否合法、以及 source/target 路径关系。
- `pt_min_seed_hours` 是否进入 cleanup 阻断判断：未进入；当前 cleanup 路径没有读取下载器 seeding 信息，也没有把 PT 做种时长接入阻断条件。
- 当前结论：不得把删除仍在做种中的 PT 资产视为已验证稳定能力；本窗口只记录风险，不扩 cleanup 行为。

## Update rule

- 每次真实私聊 smoke 完成后，立刻把对应渠道状态改成 `已完成`，并写入绝对日期。
- `Channel progress` 里的备注列必须和渠道状态一致：`待验证` 时继续写待补真实私聊 smoke 记录，并保留窗口开始日期的绝对时间锚点；`已完成` 后不得继续沿用待补文案，且必须写成 `<绝对日期> 已完成真实私聊 smoke`。
- 已完成渠道写入的真实私聊 smoke 日期不得早于窗口开始日期，也不得晚于当前结论快照日期；不要把窗口外日期回填成窗口内证据。
- 验证窗口仍在进行中时，真实私聊 smoke 的日期上界跟随“当前结论”的绝对日期前进；不要把 `最早可结束日期` 误当成后续补证的硬截止线。
- 最早可结束日期之前，`窗口活性` 保持为 `未到最早可结束日期`；`当前结论` 也要显式写出“尚未到最早可结束日期 <绝对日期>”。
- 到达最早可结束日期但退出条件未满足时，`窗口活性` 改成 `已到最早可结束日期，待补退出条件`；`当前结论` 也要显式写出“已到最早可结束日期 <绝对日期>，但退出条件仍未满足”。
- 只要四渠道里仍有待补项，`当前结论` 就必须显式写出真实私聊 cleanup smoke 仍待补，不能只写笼统的“退出条件仍未满足”。
- 当四渠道真实私聊 smoke 已全部补齐后，`当前结论` 就不得继续写“真实私聊 cleanup smoke 仍待补”；剩余缺口只写窗口日期或其他未满足项。
- 当剩余缺口已经不是渠道，而是聚合 smoke gate、cleanup 协议回归或 verification docs gate 时，`当前结论` 也必须显式写出 smoke gate、cleanup 协议或 verification docs gate 缺口，不能退化成只写日期或泛泛的“退出条件未满足”。
- 当渠道缺口和三项证据都已补齐、只剩最早可结束日期时，`当前结论` 只能保留窗口日期阻塞，不能继续捎带 smoke gate、cleanup 协议或 verification docs gate 缺口文案。
- 已完成后，`当前结论` 只能保留已满足退出条件，不得继续残留待补、缺口或日期阻塞文案。
- `当前 cleanup 协议观察` 也必须跟随渠道缺口同步收缩；只要四渠道里仍有待补项，可以写“当前缺口只剩四渠道真实私聊 smoke 证据”，但渠道全部补齐后就不得继续沿用这句旧缺口文案。
- 当渠道缺口已经补齐、剩余缺口收缩到 smoke gate、cleanup 协议回归或 verification docs gate 时，`当前 cleanup 协议观察` 也必须显式点名对应缺口，不能只删除旧文案却不写清还差什么。
- 当渠道缺口和三项证据都已补齐、只剩最早可结束日期时，`当前 cleanup 协议观察` 只能保留“未见协议回退”，不能继续残留 smoke gate、cleanup 协议或 verification docs gate 缺口文案。
- 已完成后，`当前 cleanup 协议观察` 只能保留未见协议回退，不得继续残留缺口、待补或其他退出条件文案。
- 已完成后，`当前 cleanup 协议观察` 也不得继续残留 `尚未到最早可结束日期`、`已到最早可结束日期` 或 `真实私聊 cleanup smoke` 待补这类进行中窗口文案。
- 退出条件满足后，`当前状态` 改成 `已完成`，`窗口活性` 改成 `已满足退出条件`，`当前结论` 同步写成已满足退出条件。
- 一旦到达最早可结束日期，且四渠道真实私聊 smoke、smoke gate、cleanup 协议回归三类退出条件都已满足，就必须立刻改成 `已完成`，不能继续挂在进行中。
- 一旦把验证窗口写成 `已完成`，exit checklist 里的 `tests/test_cleanup_cross_channel_smoke.py`、cleanup 协议回归和 verification docs gate 三项也必须同时保持勾选，不能出现“状态已完成但证据项未完成”。
- 即使四渠道真实私聊 smoke 和协议回归项都已补齐，也不得早于最早可结束日期把验证窗口标记为 `已完成`。
- 验证窗口仍在进行中时，`当前结论`、最近一次聚合 smoke gate、cleanup 协议回归验证和 verification docs gate 日期必须同步到当天日期；只有窗口已完成后，才允许保留完成日快照。
- 每次重跑 `tests/test_cleanup_cross_channel_smoke.py`、focused cleanup 回归集或 verification docs gate 后，立刻把最新日期、结果和命令同步写回这份台账，并同步勾选或取消 exit checklist 里的 smoke gate / cleanup 协议 / verification docs gate 三项。
- 如果 smoke 暴露回归，只允许记录并修 shared runtime、渠道胶水或显式中文日志缺口，不新增 cleanup 行为。
- `docs/STATUS.md` 只保留当前窗口快照；这份文件负责保留当前窗口的逐项证据。
