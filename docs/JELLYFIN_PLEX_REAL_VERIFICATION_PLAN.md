# Jellyfin / Plex real verification plan (v1)

> 目的：先把 “Jellyfin / Plex 真实联调值不值得升成下一条 promoted 主线” 这件事收成一个可执行的小闭环，而不是直接扩成新的媒体服务器大工程。

## 1. 要解决的真实问题

当前代码已经能按 `MEDIA_SERVER_PROVIDER` 选择 Emby / Jellyfin / Plex refresh client，但真实联调层面还有两个空档：

1. 仓库正式本地测试栈只有 `Transmission + Emby`，`docs/TEST_ENV.md` 还没有 Jellyfin / Plex 的固定容器入口；
2. 如果用户把 `MEDIA_SERVER_PROVIDER` 设成 `jellyfin` 或 `plex`，却没补齐对应地址或 token，`app/main.py` 当前会静默把 refresh 关掉，启动阶段没有明确中文提示。

所以这条主线先做的不是“把 Jellyfin / Plex 真机全打通”，而是先回答两个问题：

- 当前仓库有没有足够清楚的 readiness 信号，知道自己能不能做真实 refresh；
- 如果还不能，系统能不能显式告诉操作者“缺的是什么”，而不是静默降级。

## 2. 当前最小闭环

第一步只收一个最小缺口：

- `MEDIA_SERVER_PROVIDER=jellyfin / plex` 但缺少必填配置时，启动装配不能静默返回 `None`
- 必须打印显式中文日志，告诉操作者是哪个 provider、缺哪类配置、建议怎么补
- focused tests 继续覆盖 Emby / Jellyfin / Plex 三路装配，不改导入成功真相

在这个最小闭环之后，再用现有 `Transmission + Emby` 测试栈确认当前“真实 refresh baseline”怎么复用；如果连这个入口都不清楚，就不应该贸然把 Jellyfin / Plex 真联调升成大主线。

## 3. Phase 顺序

1. Phase 1：补 provider 选定但配置缺失时的显式中文日志与 focused tests。
2. Phase 2：复用现有 Emby 测试栈整理真实 refresh baseline，不新增 Jellyfin / Plex 容器。
3. Phase 3：基于 Phase 1-2 的证据，决定下一条 promoted 主线是“单 provider 真实联调”还是回到 BT 更大范围能力。

## 4. Done when

当前主线视为 **已收口**，满足以下任一条即可：

1. `MEDIA_SERVER_PROVIDER=jellyfin / plex` 且缺少必填配置时，启动装配会打印显式中文日志和 `[处理建议]`，且 `.venv/bin/python -m pytest -q tests/test_main.py tests/test_refresh_media_server.py tests/test_config.py -k "media_server or refresh"` 全绿；
2. `docs/TEST_ENV.md` / `docs/NEXT_STEP.md` / `docs/STATUS.md` / `README.md` / `AGENTS.md` 一致表达“当前正式本地真实 refresh 栈只有 Emby；Jellyfin / Plex 先做 readiness 评估”；
3. 使用现有 Emby 测试栈完成一条真实 refresh baseline 记录，并能明确回答“下一条 promoted 主线是否值得切到 Jellyfin 或 Plex 单 provider 联调”。

## 5. 不做清单

- 不新增 Jellyfin / Plex Docker 测试栈
- 不改 `import_to_library` 的导入成功真相和回滚纪律
- 不扩成 Jellyfin / Plex 全量媒体管理能力对齐
- 不在这一步改 cleanup / approval / BT 批量任务协议
