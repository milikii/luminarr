# Jellyfin / Plex plan (v1)

> 目的：把 `docs/NEXT_STEP.md` 的“Jellyfin / Plex 支持”主线先设计成可落地的小 Phase，避免一上来把现有 Emby 刷新链改散。

## 1. 要解决的真实问题

当前媒体服务器刷新路径只认 Emby：

- `app/main.py` 直接读取 `EMBY_BASE_URL / EMBY_API_KEY`
- `app/clients/emby.py` 是唯一已落地的刷新 client
- `RefreshMediaServerService` 的失败提示也只提 Emby

这会带来两个问题：

1. 想接 Jellyfin / Plex 时，入口、client 和文案都会一起耦在 Emby 上；
2. 即便 Jellyfin 的刷新协议和 Emby 很接近，当前代码也没有一个明确边界能安全接进去。

所以新主线先做的不是“把三个媒体服务器一次性全接完”，而是**先把刷新 client 边界收成可扩展，再按顺序补 Jellyfin、Plex**。

## 2. 当前最小闭环

2026-04-19 已完成 Phase 1：

- 新增 `app/clients/jellyfin.py`
- 新增最小测试 `tests/test_jellyfin_client.py`
- 把 `app/main.py` 里“创建媒体服务器 refresh client”收成单独 helper，当前仍保持 Emby 默认路径不变
- `RefreshMediaServerService` 的故障提示从“检查 Emby”收窄成“检查媒体服务器”，不改导入成功真相

2026-04-19 已完成 Phase 2：

- 给 `app/main.py` 增加媒体服务器 provider 选择入口
- `app/config.py` 新增 `MEDIA_SERVER_PROVIDER`、`JELLYFIN_BASE_URL`、`JELLYFIN_API_KEY`
- 保持 Emby 兼容默认值，不要求现有部署立刻改 env
- `.venv/bin/python -m pytest -q tests/test_config.py tests/test_main.py tests/test_refresh_media_server.py tests/test_jellyfin_client.py` 得到 `52 passed`

当前最小下一步切到 Phase 3，只做 **Plex refresh baseline**：

2026-04-19 已补最小 Plex refresh client baseline：

- 新增 `app/clients/plex.py`
- 新增 `tests/test_plex_client.py`
- `.venv/bin/python -m pytest -q tests/test_plex_client.py tests/test_refresh_media_server.py` 得到 `5 passed`

2026-04-19 已完成 Phase 3 最后一步：

- 把 `app/main.py` 的 provider 选择补到 `plex`
- 把 `app/config.py` 的 provider 校验放宽到 `plex`
- 补齐 `tests/test_main.py` / `tests/test_config.py` 的 Plex 装配断言
- `.venv/bin/python -m pytest -q tests/test_config.py tests/test_main.py tests/test_refresh_media_server.py tests/test_jellyfin_client.py tests/test_plex_client.py` 得到 `56 passed`

当前主线已满足 `Done when` 第 1 条：

- `app/main.py` 已能按配置选择 Emby / Jellyfin / Plex refresh client
- Emby 兼容默认值仍保留，Jellyfin / Plex 入口都已接到独立 client
- 当前不继续外扩真实 Jellyfin / Plex 联调，`After this step` 仍保持 plugin 体系后置

这一阶段不做：

- 新 approval / import / cleanup 流程
- 自动探测媒体服务器类型
- 真实 Jellyfin / Plex 联调

## 3. Phase 顺序

1. Phase 1：Jellyfin refresh client baseline，先把 client 边界和最小测试补齐。
2. Phase 2：媒体服务器 provider 选择配置，保持 Emby 兼容默认值，不让现有部署立刻改 env。
3. Phase 3：Plex refresh baseline，只补最小刷新协议，不扩成新的媒体管理平台。

## 4. Done when

当前主线视为 **已基本完成**，触发以下任一可测量条件即停止，并通知用户切到 `After this step` 第 1 项：

1. `app/main.py` 已能按配置选择 Emby / Jellyfin / Plex 的 refresh client，`.venv/bin/python -m pytest -q tests/test_main.py tests/test_refresh_media_server.py tests/test_jellyfin_client.py tests/test_plex_client.py` 全绿；
2. 或者本轮代码变更 `< 20` 行、只是为同一个 provider 再补一条微调分支，触发 `AGENTS.md §11` 停机规则。

## 5. 不做清单

- 不改 `import_to_library` 的成功真相和回滚纪律
- 不把这一轮扩成 Jellyfin / Plex 全量功能对齐
- 不在这一步改 watchlist / btsub / cleanup / approval 协议
