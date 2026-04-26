# BT page / range plan (v19)

> 目的：记录这条 BT allowlist 页面 proof 主线是如何收口的。当前它已经完成，不再是进行中的施工计划。

## 1. 为什么当前继续留在 BT

- 2026-04-19 已确认当前主机没有可达 Plex 实例，Plex 真实 refresh smoke 值得性重评估按“暂不继续追 Plex，先回到 BT 更大范围能力”收口。
- 上一条 BT 用户页 / 编号范围页能力主线已经收口：allowlist 页面 URL 预览、聊天缓存、`bt批量确认` 复用、category/list 页面和 `p=<页码>` 语法糖都已补齐。
- 上一条“排序列表 exact URL 缓存复用 proof”已经确认命令入口、页面抓取、聊天缓存和 `bt批量确认` 复用都不回退；2026-04-20 最后一条分类排序列表 exact `?c=1_2&s=seeders&o=desc` URL 聊天缓存 proof 也已收口，这个能力族不再继续拆更小页面形式。

## 2. 当前最小闭环

当前先只收一个更保守的入口：

1. 用户发送 `bt批量 https://nyaa.si/?c=1_2&s=seeders&o=desc 1-3`；
2. 既有页面抓取保持不回退，不重新走关键词搜索；
3. 页面抓取成功后，继续复用现有去重、编号范围过滤、批量预览文本和聊天候选缓存；
4. 既有 `bt批量确认 1-3` 复用边界保持不回退，不自动 `confirm`。

当前第一步不做：

- 不让 LLM 决定该抓哪个 URL
- 不接未声明站点
- 不在这一步直接批量 dispatch
- 不把 PT 主链或媒体型 BT 入库链一起放宽

## 3. Phase 顺序

1. Phase 1：已完成 allowlist 页面 URL 识别、页面类型校验、只读批量预览。
2. Phase 2：已完成 `页面 URL + p=<页码>` 的最小语法糖。
3. Phase 3：已完成首页翻页页与排序列表页。
4. Phase 4：已完成排序页分页直达语法的 focused proof。
5. Phase 5：已完成分类页与排序参数组合页的 focused proof。
6. Phase 6：已完成分类页 + 排序参数 + `p=<页码>` 语法的 focused proof。
7. Phase 7：已完成用户页 + 排序参数组合页的 focused proof。
8. Phase 8：已完成用户页 + 排序参数 + `p=<页码>` 组合页的 focused proof。
9. Phase 9：已完成搜索页 + 排序参数组合页的 focused proof。
10. Phase 10：已完成搜索页 + 排序参数 + `p=<页码>` 组合页的 focused proof。
11. Phase 11：已完成搜索页 + `p=<页码>` 组合页的 focused proof。
12. Phase 12：已完成搜索页 + `p=<页码>`、但不带分类参数的 focused proof。
13. Phase 13：已完成搜索页无分类基础页的 focused proof。
14. Phase 14：已完成分类基础页的 focused proof。
15. Phase 15：已完成分类搜索基础页的 focused proof。
16. Phase 16：已完成首页基础页的 focused proof。
17. Phase 17：已完成无分类用户基础页的 focused proof。
18. Phase 18：已完成无分类用户分页组合页的 focused proof。
19. Phase 19：已完成无分类用户排序组合页的 focused proof。
20. Phase 20：已完成无分类用户排序分页组合页的 focused proof。
21. Phase 21：已完成无分类用户排序显式分页 URL 的 focused proof。
22. Phase 22：已完成无分类用户显式分页 URL 的 focused proof。
23. Phase 23：已完成带分类用户显式分页 URL 的 focused proof。
24. Phase 24：已完成带分类用户排序显式分页 URL 的 focused proof。
25. Phase 25：已完成分类排序显式分页 URL 的 focused proof。
26. Phase 26：已完成排序显式分页 URL 的 focused proof。
27. Phase 27：已完成搜索排序显式分页 URL 的 focused proof。
28. Phase 28：已完成首页显式分页 URL 的 focused proof。
29. Phase 29：已完成分类列表显式分页 URL 的 focused proof。
30. Phase 30：已完成分类基础页显式分页 URL 的 focused proof。
31. Phase 31：已完成分类搜索显式分页 URL 的 focused proof。
32. Phase 32：已完成分类搜索基础页 exact URL 的 focused proof。
33. Phase 33：已完成排序列表 exact URL 的缓存复用 focused proof。
34. Phase 34：已完成分类排序列表 exact URL 的聊天缓存 focused proof；如果后续还要补更多站点或页面形式，再单独扩规则，不在这一条里顺手平台化。

2026-04-20 当前进度：

- 已完成项保持不回退：allowlist 页面 URL 识别、页面类型校验、只读批量预览、聊天候选缓存、Telegram 路由证明、`bt批量确认` 复用 proof、category/list 页面、首页翻页页、排序列表页，以及 `页面 URL + p=<页码>` 语法糖；
- 同日 focused tests 已确认：`https://nyaa.si/?s=seeders&o=desc` 已继续写入现有聊天缓存，并继续复用 `bt批量确认` 边界；随后更小的 `https://nyaa.si/?c=1_2&s=seeders&o=desc` 分类排序列表 exact URL 聊天缓存 proof 也已收口；
- `https://nyaa.si/?c=1_2&q=frieren&p=2` 已完成 focused proof，证明更小的分类搜索显式分页 exact URL 也仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?c=1_2&p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?f=0&c=1_2&p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc&p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?s=seeders&o=desc&p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?s=seeders&o=desc p=2` 已完成 focused proof，证明它会从命令入口直达现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?c=1_2&s=seeders&o=desc&p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?c=1_2&s=seeders&o=desc` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?c=1_2&s=seeders&o=desc p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?f=0&c=1_2&u=subsplease&p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc&p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?f=0&c=1_2&q=frieren&p=2` 已完成 focused proof，证明更严格的分类搜索显式分页变体仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?c=1_2&q=frieren` 已完成 focused proof，证明更小的分类搜索基础页 exact URL 也仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?q=frieren&p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?q=frieren` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?c=1_2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?f=0&c=1_2&q=frieren` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?u=subsplease` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?u=subsplease p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?u=subsplease&p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?u=subsplease&s=seeders&o=desc` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?u=subsplease&s=seeders&o=desc p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2` 已完成 focused proof，证明它仍走现有 allowlist 页面预览链，并继续复用 `bt批量确认` 边界；
- `bt批量 https://nyaa.si/?c=1_2&s=seeders&o=desc 1-2` 已完成 focused proof，证明它会继续写入现有聊天缓存，并继续复用 `bt批量确认` 边界；
- 若后续继续 BT，只按 `docs/NEXT_STEP.md` 的 `After this step` 第 1 项，从现有 allowlist 里再挑一个更小页面形式单独开主线；
- 未声明排序参数、未声明页面、未声明站点和非法范围仍必须显式中文拒绝，不静默去抓未知页面。

## 4. Done when

当前主线视为 **已收口**，并已在 2026-04-20 满足 `Done when` 第 1、2 条；下面保留这条主线的收口判据：

1. `bt批量 https://nyaa.si/?c=1_2&s=seeders&o=desc 1-3` 的 exact URL 预览候选已被证明会继续写入现有聊天缓存；对应 focused tests 全绿；
2. 上述分类排序列表 exact URL 的候选已被证明不会破坏现有 `bt批量确认` 复用边界；对应 focused tests 全绿；
3. 本轮代码变更 `< 20` 行且只是对同一个 page/range helper 再补一条 `if/elif/log` 诊断分支，触发 `AGENTS.md §11` 停机规则。

## 5. 不做清单

- 不做自动 `confirm`
- 不做未知站点 / 动态站点 / CAPTCHA / 登录态页面
- 不把这一步扩成通用插件平台
- 不改现有 downloader approval / confirm / lease/version / SQLite 真相边界
