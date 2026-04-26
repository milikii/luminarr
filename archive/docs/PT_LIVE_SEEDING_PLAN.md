# PT live seeding plan (v1)

> 目的：把 cleanup 当前“只看 `completion_observed_at`”的保守时间窗，升级成“优先看 downloader live seeding 真相；拿不到时继续 fail-closed”的最小主线。

## 1. 要解决的真实问题

当前 cleanup PT 保护窗口已经能挡住“下载刚完成就删源文件”的风险，但它看的是真相仍然偏保守：

- 现在只看 `download_monitor.completion_observed_at`
- 这能回答“什么时候第一次观察到下载完成”
- 但不能回答“下载器当前到底已经做种了多久”

结果就是两种情况会混在一起：

1. 实际已经安全做种足够久，但系统仍只能按完成观察时间保守阻断；
2. 下载器侧真相缺失时，系统只能继续 fail-closed，但不知道缺的是“完成时间”还是“live seeding”。

所以这条主线的目标不是放宽 cleanup，而是**把 downloader live seeding 真相接进来，并继续守住 fail-closed**。

## 2. 当前最小闭环

当前只做最小 PT 保护闭环：

1. 下载器 client 暴露“当前 seeding 秒数 / seeding 起始时间 / 是否仍在做种”的最小只读字段；
2. cleanup PT guard 优先读取 downloader live seeding 真相；
3. 若真相存在，则按 live seeding 秒数判断 `pt_min_seed_hours`；
4. 若真相缺失、格式异常或下载器不支持，则继续显式中文日志 + fail-closed；
5. 不改 cleanup 删除范围，不新增 workflow，不把 PT 主链和 BT 支线揉在一起。

## 3. Phase 顺序

1. Phase 1：为 Transmission / qBittorrent status 协议补统一的 live seeding 字段出口。
2. Phase 2：cleanup PT guard 先读 live seeding 真相，拿不到时再显式回退到现有 fail-closed 路径。
3. Phase 3：补 focused tests，覆盖“真相存在 / 真相缺失 / 真相格式异常 / 未达到最小做种时长”。
4. Phase 4：若本机测试环境支持，补一次真实 downloader focused verification。

## 4. Done when

当前主线视为 **已收口**，满足以下任一条即可：

1. `tests/test_cleanup_downloaded_source.py -k pt_seed_window` 和下载器状态 focused tests 全绿，且 cleanup PT guard 能优先使用 live seeding 真相；
2. Transmission / qBittorrent 两个协议里至少当前 PT 角色绑定使用的协议已经接入 live seeding 真相，另一个只差同构收尾；
3. 本轮代码变更 `< 20` 行且只是对同一 downloader 状态字段再补一条 `if/elif/log` 诊断分支，触发 `AGENTS.md` 收益递减停机线。

## 5. 不做清单

- 不放宽 cleanup 删除范围
- 不把“拿不到 live seeding 真相”改成乐观放行
- 不新增自动 confirm、自动 cleanup 或其他新 workflow
- 不把这一步扩成 Jellyfin / Plex 联调、BT 批量任务或字幕能力主线
