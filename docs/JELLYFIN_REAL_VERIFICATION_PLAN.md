# Jellyfin real verification plan (v1)

> 目的：把 Jellyfin 从“已能选 provider、但还没进入真实联调”推进到一个更具体、可继续施工的单 provider 主线，同时不把 Plex 一起绑进来。

## 1. 为什么先选 Jellyfin

在现有三个 refresh client 里，Jellyfin 是最保守的一条：

- `app/clients/emby.py` 和 `app/clients/jellyfin.py` 都走 `POST /Library/Refresh`
- 两者都用 API token，只是 Emby 走 query param，Jellyfin 走 header
- `plex.py` 的刷新入口、参数形状和后续排障习惯都更不一样

所以当上一条 “Jellyfin / Plex 真实联调重评估” 主线确认“值得继续选单 provider”之后，最小风险的下一条 promoted 主线就是先收 Jellyfin。

## 2. 当前最小闭环

当前最小缺口不是新协议，而是**可观测性仍太泛**：

- refresh 成功/失败日志还只写“媒体库刷新”
- 后续如果用户真的把 provider 切到 Jellyfin，排障时仍要先回头猜“这次失败到底是哪一个 provider”

所以这一步先只做：

- 把 refresh service 的失败日志带上 provider 名称
- 保持返回给用户的成功/失败文本边界不变，不改导入成功真相
- focused tests 继续覆盖 `app/main.py -> RefreshMediaServerService` 这条装配线

2026-04-19 已完成 Phase 1：

- `RefreshMediaServerService` 的失败日志现在会带 `provider=jellyfin / plex / emby`
- `app/main.py` 在装配 refresh service 时会把当前 provider 传进去
- `.venv/bin/python -m pytest -q tests/test_main.py tests/test_refresh_media_server.py -k "refresh"` 得到 `9 passed, 17 deselected`

## 3. Phase 顺序

1. Phase 1：补 refresh 失败日志里的 provider 可观测性。
2. Phase 2：如果后续有 Jellyfin 实例，再做单 provider 真实 refresh smoke。
3. Phase 3：根据 Jellyfin 真实 smoke 结果，再决定是否值得继续扩到 Plex。

## 4. Done when

当前主线视为 **已收口**，满足以下任一条即可：

1. refresh 失败日志已带 `provider=jellyfin` 等显式字段，且 `.venv/bin/python -m pytest -q tests/test_main.py tests/test_refresh_media_server.py -k "refresh"` 全绿；
2. `docs/NEXT_STEP.md` / `docs/STATUS.md` / `README.md` / `AGENTS.md` / `docs/JELLYFIN_REAL_VERIFICATION_PLAN.md` 一致表达“当前主线是 Jellyfin 单 provider 真实联调预备”；
3. 本轮代码变更 `< 20` 行且只是对同一个 refresh 路径补一条诊断日志分支，触发 `AGENTS.md §11` 停机规则。

## 5. 不做清单

- 不把这一步重新放大成 Jellyfin + Plex 双线并行
- 不新增 Jellyfin Docker 测试栈
- 不改 `import_to_library` 的导入成功真相或回滚纪律
- 不扩成 Jellyfin 全量媒体管理能力
