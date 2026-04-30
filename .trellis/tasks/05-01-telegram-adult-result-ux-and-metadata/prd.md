# Telegram 结果交互与成人 metadata 主辅源重排

## Goal

把当前 `成人搜` / adult-only BT 结果从“能返回资源”推进到“结果可读、可点、信息完整”，并同步重排成人 metadata 主辅源策略。

## What I already know

* 当前 `成人搜` 已经不会卡在通用只读空结果；当已配置 adult-only 源有结果时，Telegram 已能回资源。
* 用户当前最关心的不是再扩搜索边界，而是把 Telegram 结果交互做得更好看、更好用。
* 用户明确要求优先优化：
  - 消息排版
  - Telegram 中磁力链接可点击/可复制
  - 海报 + 各种标准信息
* 用户明确认为 `javbus` 不适合作为主力 metadata helper，原因是海报质量差。
* 用户明确认为这些来源值得优先参考：
  - `avmoo.shop`
  - `avbase.net`
  - `jav321.com`
  - `avsox.click`
  - `caribbeancom.com`
  - `missav123.com`
* 用户明确知道 `DMM / FANZA` 质量高，但需要日本 IP，因此更适合作为条件增强源，而不是默认主源。

## Requirements (initial)

* Telegram adult search result 要有更清晰的排版层级。
* Telegram 返回的磁力链接应尽量支持直接点击/复制。
* 结果里要补齐海报和标准信息字段。
* metadata 主辅源要重新排序，`javlibrary` 降为 backup/cross-check，`javbus` 不再默认作为主源。

## Acceptance Criteria (initial)

* [x] Telegram 里成人搜索结果的排版显著优于当前纯文本清单。
* [x] Telegram 结果里磁力链接或等价链接可直接点击/复制。
* [x] 结果里有稳定的海报 + 标准信息字段。
* [x] metadata 源主辅策略有明确结论，并被实现或至少被结构化接入到代码/设计中。

## Implementation result

* `成人搜` direct adult-only 命中现在和 fallback 命中统一走 `成人资源候选` 输出，不再显示通用 `BT 只读探索结果` 壳。
* Telegram formatter 会把成人候选重排为 `【成人资源候选】`、候选编号块、海报、标准信息、metadata source 和裸磁力链接；旧的 `链接参考` 摘要不再占用 Telegram 结果主视图。
* JavLibrary helper 仅作为 `backup_cross_check` metadata 来源继续补全，并能解析/传播 poster、发行日、时长、制作商、系列、导演、类别和演员字段。
* metadata source policy 已结构化为默认主源优先：`avmoo`、`avbase`、`jav321`、`avsox`、`caribbeancom`、`missav`；`javlibrary` 为 backup/cross-check，`javbus` 为 supporting 且不进入默认主源，`fanza` 为 conditional。

## Out of Scope

* 不重做 PT 主链搜索
* 不把当前 adult-only 搜索边界扩成全站爬虫
* 不在这一轮处理所有潜在 metadata 站点，只做最有价值的主辅源排序和首批接入

## Open Questions

* 第一轮应该先做到“Telegram 结果排版 + 可点击磁力链接 + 单一主海报源”，还是连主辅源切换一起落地？
