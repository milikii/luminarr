# Jellyfin / Plex real verification plan (v2)

> 目的：在 Jellyfin 单 provider 真实 smoke 已收口之后，继续回答“Plex 真实 refresh smoke 还值不值得补做”，而不是直接扩成新的媒体服务器大工程。

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

2026-04-19 已完成 Phase 1：

- `MEDIA_SERVER_PROVIDER=jellyfin / plex` 但缺少必填配置时，`app/main.py` 不再静默返回 `None`
- 启动装配会打印显式中文 `[媒体服务器配置缺失]` 与 `[处理建议]`
- `.venv/bin/python -m pytest -q tests/test_main.py tests/test_refresh_media_server.py tests/test_config.py -k "media_server or refresh"` 得到 `10 passed, 46 deselected`
- 同日追加当前主机 Plex 探针：`curl http://127.0.0.1:32400/identity` 返回 `000`，说明本机没有自动发现到可达 Plex 实例；在没有真实实例前，继续追 Plex smoke 的收益低于回到 BT 更大范围能力

## 3. Phase 顺序

1. Phase 1：补 provider 选定但配置缺失时的显式中文日志与 focused tests。
2. Phase 2：基于 Jellyfin smoke 已收口和 Plex 入口探针结果，决定 Plex 是否还值得继续追真实实例。当前进行中。
3. Phase 3：如果当前批次仍无 Plex 实例，就回到 BT 更大范围能力；只有后续单独拿到实例时才再开 Plex smoke 主线。

## 4. Done when

当前主线视为 **已收口**，满足以下任一条即可：

1. `MEDIA_SERVER_PROVIDER=jellyfin / plex` 且缺少必填配置时，启动装配会打印显式中文日志和 `[处理建议]`，且 `.venv/bin/python -m pytest -q tests/test_main.py tests/test_refresh_media_server.py tests/test_config.py -k "media_server or refresh"` 全绿；
2. 当前主机未自动发现到可达 Plex 实例，且 `docs/NEXT_STEP.md` / `docs/STATUS.md` / `README.md` / `AGENTS.md` 一致表达“当前批次不继续追 Plex 真实 smoke，下一步回到 BT 更大范围能力”；
3. 如果后续单独拿到 Plex 实例，再完成一次真实 Plex refresh smoke，并明确记录成功或失败证据。

## 5. 不做清单

- 不新增 Jellyfin / Plex Docker 测试栈
- 不改 `import_to_library` 的导入成功真相和回滚纪律
- 不扩成 Jellyfin / Plex 全量媒体管理能力对齐
- 不在这一步改 cleanup / approval / BT 批量任务协议
