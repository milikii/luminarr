# App main slimming log (v1)

> 目的：承接当前“`app/main.py` 启动装配 / 下载器路由 helper 瘦身 / 模块化”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 当前主线状态：`app/main.py` 启动装配 / 下载器路由 helper 瘦身 / 模块化已在 2026-04-19 通过 `app/downloader_route_lookup.py` helper 抽离满足 `Done when` 第 1 条，focused tests `16 passed, 1 deselected`
- 上一条已完成主线“`private_chat_runtime.py` shared runtime 编排层瘦身 / 模块化”已在 2026-04-19 满足 `Done when` 第 2 条：入站 trace 和回包 trace 已抽到 `_log_private_chat_inbound()` / `_wrap_reply_with_trace()` helper，focused tests `34 passed, 17 deselected`
- 再上一条已完成主线“`cleanup_downloaded_source.py` cleanup 编排层瘦身 / 模块化”已在 2026-04-19 满足 `Done when` 第 1 条：`app/services/cleanup_correlation_lookup.py` 已承接“查询引用 -> 任务身份 -> import 关联”边界
- 下一条主线已切到 `series / anime` 独立名称解析最小实现；蓝图见 `docs/SERIES_ANIME_NAMING_PLAN.md`，详细闭环见 `docs/SERIES_ANIME_NAMING_LOG.md`

## 2. Risk groups

### 2.1 下载器路由查询 / client 解析

当前风险：
- `app/main.py` 仍把 task_ref -> downloader_name 查询、payload 解析、client 选择和 status/import source 路由揉在同一段启动文件里；这一步只允许把“查任务真相 -> 选下载器 client -> 调对应协议”收成连贯 helper。
- 这一组继续守住下载器角色绑定、历史任务里的 `downloader_name` 和现有 fail-closed 中文日志边界。

已完成闭环：
- 2026-04-19 已先把 “task_ref/chat_id -> downloader_name” 查询、payload 解析和对应中文 fail-closed 日志抽到 `app/downloader_route_lookup.py`；`app/main.py` 先减掉一段共享路由查询逻辑，status/import source 的 client 解析仍留待下一轮同组收口。
- 2026-04-19 已继续把实例缺失 / client 未配置 / 路由调用 `get_torrent_status` / `get_torrent_import_source` 一并合并进 `app/downloader_route_lookup.py`；`app/main.py` 这一组只剩装配调用点。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_main.py -k "resolve_downloader_name_for_task or resolve_downloader_client_for_lookup or resolve_downloader_client_for_dispatch or get_torrent_status_with_routing or get_torrent_import_source_with_routing"`

### 2.2 client / service 装配

当前风险：
- `main()` 里仍内联装配 SQLite repo、TMDB/Fanart、Transmission/qBittorrent、BT source adapter 和各 service；这一步只允许把“配置 -> client/service 对象”收成小 helper，不改对象关系。
- 这一组继续守住谁调用谁的关系：启动入口读 `settings`，再把 repo/client/service 串起来交给 shared runtime 和各渠道入口。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_main.py -k "run_application_polling"`
- `.venv/bin/python -m pytest -q tests/test_config.py -k "requires_token or requires_transmission_base_url or defaults_role_binding_to_first_instance or reads_tmdb_settings"`

### 2.3 可选渠道绑定 / 启动入口日志

当前风险：
- `build_application(...)` 之后的 `bot_data` 写入、Feishu 长连接 / webhook 二选一绑定、WeCom webhook 配置和最终 polling 启动还堆在 `main()` 尾部；这一步只允许把“application 已建好后再挂哪些可选能力”收成 helper。
- 这一组继续守住四渠道入口共用同一 shared runtime，不新增新的生命周期框架或后台总线。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_main.py tests/test_telegram_bot.py -k "run_application_polling or build_application"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_main.py -k "resolve_downloader_name_for_task or resolve_downloader_client_for_lookup or resolve_downloader_client_for_dispatch or get_torrent_status_with_routing or get_torrent_import_source_with_routing"`
- `.venv/bin/python -m pytest -q tests/test_main.py tests/test_telegram_bot.py -k "run_application_polling or build_application"`
- `.venv/bin/python -m pytest -q tests/test_config.py -k "requires_token or requires_transmission_base_url or defaults_role_binding_to_first_instance or reads_tmdb_settings"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.3 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 该主线已完成；后续只保留完成态路径和 focused tests，下一条主线按 `docs/NEXT_STEP.md` 推进。
