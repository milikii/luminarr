# BT page / range plan (v5)

> 目的：在已完成的用户页 / 列表页 / 编号范围页能力基础上，只补一个更小的“排序页 + `p=<页码>` 直达语法 proof”，继续复用既有 approval -> confirm -> jobs 真相边界。

## 1. 为什么当前继续留在 BT

- 2026-04-19 已确认当前主机没有可达 Plex 实例，Plex 真实 refresh smoke 值得性重评估按“暂不继续追 Plex，先回到 BT 更大范围能力”收口。
- 上一条 BT 用户页 / 编号范围页能力主线已经收口：allowlist 页面 URL 预览、聊天缓存、`bt批量确认` 复用、category/list 页面和 `p=<页码>` 语法糖都已补齐。
- 上一条“更多 allowlist 页面类型再评估”已经确认现状先不再扩页面家族；当前更小也更保守的缺口，只剩排序列表页和 `p=<页码>` 组合语法的端到端 proof。

## 2. 当前最小闭环

当前先只收一个更保守的入口：

1. 用户发送 `bt批量 https://nyaa.si/?s=seeders&o=desc p=2 1-3`；
2. parser / routing 明确识别这仍然是 BT allowlist 页面请求，而不是普通关键词；
3. 解析阶段把 `p=2` 追加回排序页 URL，继续走现有页面抓取；
4. 页面抓取成功后，继续复用现有去重、编号范围过滤、批量预览文本和候选缓存；
5. 后续 `bt批量确认 1-3` 仍复用既有单条 approval / confirm / jobs 边界，不自动 `confirm`。

当前第一步不做：

- 不让 LLM 决定该抓哪个 URL
- 不接未声明站点
- 不在这一步直接批量 dispatch
- 不把 PT 主链或媒体型 BT 入库链一起放宽

## 3. Phase 顺序

1. Phase 1：已完成 allowlist 页面 URL 识别、页面类型校验、只读批量预览。
2. Phase 2：已完成 `页面 URL + p=<页码>` 的最小语法糖。
3. Phase 3：已完成首页翻页页与排序列表页。
4. Phase 4：当前只补排序页分页直达语法的 focused proof；如果后续还要补更多站点或页面形式，再单独扩规则，不在这一条里顺手平台化。

2026-04-19 当前进度：

- 已完成项保持不回退：allowlist 页面 URL 识别、页面类型校验、只读批量预览、聊天候选缓存、Telegram 路由证明、`bt批量确认` 复用 proof、category/list 页面、首页翻页页、排序列表页，以及 `页面 URL + p=<页码>` 语法糖；
- 当前只补 `https://nyaa.si/?s=seeders&o=desc p=2` 这条直达语法 proof，证明它仍会落到现有 allowlist 页面预览链；
- 未声明排序参数、未声明页面、未声明站点和非法范围仍必须显式中文拒绝，不静默去抓未知页面。

## 4. Done when

当前主线视为 **已收口**，满足以下任一条即可：

1. `bt批量 https://nyaa.si/?s=seeders&o=desc p=2 1-3` 已能返回只读批量预览，并证明命令入口会直接走页面抓取；对应 focused tests 全绿；
2. 上述直达语法的候选已被证明可继续复用 `bt批量确认` 所需的聊天缓存边界，且未声明排序参数仍保持中文拒绝；对应 focused tests 全绿；
3. 本轮代码变更 `< 20` 行且只是对同一个 page/range helper 再补一条 `if/elif/log` 诊断分支，触发 `AGENTS.md §11` 停机规则。

## 5. 不做清单

- 不做自动 `confirm`
- 不做未知站点 / 动态站点 / CAPTCHA / 登录态页面
- 不把这一步扩成通用插件平台
- 不改现有 downloader approval / confirm / lease/version / SQLite 真相边界
