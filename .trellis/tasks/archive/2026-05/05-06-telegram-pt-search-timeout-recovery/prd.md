# telegram pt real-smoke search timeout recovery

## Goal

让 Telegram 里的 PT 搜索在真实环境遇到上游超时或搜索源失败时，不要把整条搜索链直接打死；优先继续尝试可用查询路径，并把“部分失败”和“彻底失败”区分开来。

## What I already know

* 当前任务目录已存在，但之前还没有 `prd.md`，说明这条线一直停在 planning。
* PT 搜索请求路径当前会走 `app/services/search_request_context.py` 里的 `_search_candidates_with_logging()`。
* 这段逻辑当前对 `httpx.HTTPError` 和 `json.JSONDecodeError` 是：
  - 记录 `搜索源查询失败`
  - 然后直接 `raise`
* 直接 `raise` 的结果是：只要搜索源在某次查询上抛异常，后续 `ordered_queries` 不会继续尝试，Telegram PT 搜索链会被整段打断。
* 当前日志文案已经明确区分“这不是正常无候选”：
  - `检查 Prowlarr/BT 来源、代理和网络连通性；当前搜索未拿到结果，且这不是正常的“无候选”状态。`
* 当前 repo 已经有“容忍单个外部 helper 失败但保留主结果”的先例：
  - `tests/test_search_media.py::test_search_bt_read_only_and_format_keeps_results_when_javlibrary_lookup_fails`
* 当前项目里和 timeout 相关的外部搜索客户端主要是：
  - `app/clients/prowlarr.py`
  - 以及通过 `raw_search_func` 间接接入的 BT 来源搜索

## Assumptions (temporary)

* 本轮主要针对 Telegram/PT 搜索路径，不扩展到字幕、metadata、refresh 等其他 timeout 处理。
* 本轮不修改 Telegram PT 资源卡 UI 结构，只处理搜索超时后的恢复语义和用户可见反馈。
* 本轮优先做 fail-soft：若部分查询超时但后续查询还能拿到结果，就继续给用户结果，而不是整段失败。

## Open Questions

* 当前无阻塞性开放问题；用户已确认采用“部分超时但仍有结果时，返回候选并附轻提示”。

## Requirements (evolving)

* PT 搜索遇到单次上游 timeout / HTTP 异常时，不应无条件中断整条 `ordered_queries` 搜索。
* 若后续 query 还能拿到候选结果，应继续返回候选，不把这次搜索误判成整体失败。
* 当前面的 query 超时、后面的 query 成功时，用户侧需要附一行轻提示，明确“部分搜索源超时，结果可能不完整”。
* 若所有 query 都失败或都超时，仍要明确区分：
  - “正常无候选”
  - “搜索源异常/超时”
* 运维日志必须保留异常细节，不能因为 fail-soft 就静默吞错。
* 需要有 focused tests 覆盖：
  - 前一条 query 超时、后一条 query 成功
  - 全部 query 超时/失败
  - 正常无候选不被误报成 timeout

## Acceptance Criteria (evolving)

* [ ] Telegram/PT 搜索在部分 query timeout 时仍能继续尝试后续 query。
* [ ] 后续 query 成功时，用户仍能拿到正常候选结果。
* [ ] 部分 query timeout 但仍有候选时，用户会看到轻提示，不把结果伪装成完全正常。
* [ ] 全部 query 失败时，用户拿到的是“搜索异常/超时”而不是“无候选”。
* [ ] focused tests 覆盖 timeout recovery 与正常无候选的分界。

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* 不改 Telegram PT 资源卡样式和交互按钮结构。
* 不做新的搜索 provider 接入。
* 不扩展为通用“所有外部服务 timeout 恢复框架”。
* 不改字幕 provider / metadata scraper / refresh media server 的 timeout 处理。

## Technical Notes

* 核心现状：
  - `app/services/search_request_context.py::_search_candidates_with_logging()`
* 相关搜索行为与回归：
  - `tests/test_search_media.py`
* 相关外部搜索客户端：
  - `app/clients/prowlarr.py`
