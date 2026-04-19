# Jellyfin real verification plan (v2)

> 目的：把 Jellyfin 从“已能选 provider、失败日志已带 provider”推进到“有一条真实 refresh smoke 证据，或失败已可直接定位”的单 provider 主线，同时不把 Plex 一起绑进来。

## 1. 为什么先选 Jellyfin

在现有三个 refresh client 里，Jellyfin 是最保守的一条：

- `app/clients/emby.py` 和 `app/clients/jellyfin.py` 都走 `POST /Library/Refresh`
- 两者都用 API token，只是 Emby 走 query param，Jellyfin 走 header
- `plex.py` 的刷新入口、参数形状和后续排障习惯都更不一样

所以当上一条 “Jellyfin / Plex 真实联调重评估” 主线确认“值得继续选单 provider”之后，最小风险的下一条 promoted 主线就是先收 Jellyfin。

## 2. 当前最小闭环

当前最小缺口不是新协议，而是**还缺一条真实 smoke 证据**：

- 当前代码已经能按配置切到 Jellyfin refresh client
- 失败日志也已经带 `provider=jellyfin / plex / emby`
- 但仓库里还没有一条“Jellyfin 单 provider 真实 refresh 已打通 / 或失败点已收清”的最新闭环记录

所以这一步先只做：

- 用已有 Jellyfin 实例做一次单 provider 真实 refresh smoke
- 如果 smoke 失败，先把 provider / base_url / HTTP 结果或异常原因打清楚
- 保持返回给用户的成功/失败文本边界不变，不改导入成功真相

2026-04-19 已完成 Phase 1：

- `RefreshMediaServerService` 的失败日志现在会带 `provider=jellyfin / plex / emby`
- `app/main.py` 在装配 refresh service 时会把当前 provider 传进去
- `.venv/bin/python -m pytest -q tests/test_main.py tests/test_refresh_media_server.py -k "refresh"` 得到 `9 passed, 17 deselected`
- 同日追加真实 smoke 失败探针（一次性临时脚本已删除）：命中 `provider=jellyfin target=http://127.0.0.1:8096 request_url=http://127.0.0.1:8096/Library/Refresh 错误=All connection attempts failed`，当前失败点已可直接定位到目标地址和请求路径

## 3. Phase 顺序

1. Phase 1：补 refresh 失败日志里的 provider 可观测性。已完成。
2. Phase 2：用现有 Jellyfin 实例做单 provider 真实 refresh smoke。2026-04-19 已完成一次真实失败探针，当前失败点已可直接定位；该条主线可按失败可观测性出口收口。
3. Phase 3：根据 Jellyfin 真实 smoke 结果，再决定是否值得继续扩到 Plex。

## 4. Done when

当前主线视为 **已收口**，满足以下任一条即可：

1. 在已有 Jellyfin 实例上完成一次真实 refresh smoke，并把成功证据写回当前快照或当前蓝图；
2. 真实 refresh smoke 失败，但 provider / base_url / HTTP 结果或异常原因已经可直接定位，且 `.venv/bin/python -m pytest -q tests/test_main.py tests/test_refresh_media_server.py -k "refresh"` 全绿；
3. 本轮代码变更 `< 20` 行且只是对同一个 refresh 路径补一条诊断日志分支，触发 `AGENTS.md §11` 停机规则。

## 5. 不做清单

- 不把这一步重新放大成 Jellyfin + Plex 双线并行
- 不新增 Jellyfin Docker 测试栈
- 不改 `import_to_library` 的导入成功真相或回滚纪律
- 不扩成 Jellyfin 全量媒体管理能力
