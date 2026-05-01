# brainstorm: adult search fallback when read-only misses

## Goal

让 `成人搜 <番号>` 在当前“只读探索未找到候选”时，不要直接卡死在只读结果为空，而是继续尝试返回可用资源。

## What I already know

* 当前 Telegram 宿主已恢复可用，`成人搜 SSIS-483` 能正常进入应用并回包。
* 当前 `.env` 里 `BT_WEB_SOURCES=` 为空，`成人搜` 只读链当前只剩 `Prowlarr` 这一路。
* 直接调用当前 `ProwlarrClient.search("SSIS-483")` 返回 `0` 条结果。
* 用户明确要求：“只读角色不明中，就直接搜资源，总之不能卡在只读，要返回资源。”
* 用户刚刚进一步明确：`成人搜` 只允许搜索成人 BT 站点和指定的 Prowlarr 成人索引器，绝不能回落到 PT 主链搜索。

## Assumptions (temporary)

* 用户更在意“有成人资源结果可看”，但不接受跨到 PT 主链搜索。
* fallback 必须保持在 adult-only BT 搜索边界内。

## Open Questions

* 无。用户已确认：当当前已配置的成人来源都返回空结果时，不扩大到未配置来源，只在当前 adult-only 搜索边界内处理。

## Requirements (evolving)

* 当 `成人搜 <query>` 的当前只读探索结果为空时，继续尝试返回资源，不要只回复“未找到候选”。
* fallback 只能使用成人 BT 站点和指定的 Prowlarr 成人索引器，不能进入 PT 主链搜索。
* 当当前已配置的 adult-only 来源都为空时，明确返回“当前成人源无结果”，而不是扩大到未配置来源。

## Acceptance Criteria (evolving)

* [ ] `成人搜` 在只读结果为空时，仍能给出可操作的资源结果或明确的下一步，而不是停在只读空结果。

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* 不重做整条成人搜索架构
* 不顺手改非成人搜索主线
* 不把 `成人搜` 回落到 PT 搜索
* 不在这一轮扩新的站点源

## Technical Notes

* 当前相关入口：`SearchMediaService`、BT read-only display/runtime、Telegram private chat runtime
* 当前现象已由真实 Telegram 消息验证：`成人搜 SSIS-483` -> `BT 只读探索未找到候选：SSIS-483`
