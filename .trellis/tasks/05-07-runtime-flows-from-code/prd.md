# document runtime flows from code

## Goal

从当前仓库真实代码、现有架构文档和测试入口反推 Luminarr 的完整功能流程，并用 `docs/flows/` 反向纠偏顶层真相文档。输出不仅包括 `docs/flows/` 下的流程文档集合，还包括把 `docs/PRD.md`、`docs/ARCHITECTURE.md`、`docs/NEXT_STEP.md`、`docs/STATUS.md`、`docs/INDEX.md` 和相关 docs gate 更新到与代码一致的状态；在收尾验证阶段，再顺手修复本轮暴露出的 3 个既有红灯，使仓库重新回到可验证状态。

## What I already know

* 当前最贴近代码的运行时真相已经落在 `docs/flows/` 和 `.trellis/spec/backend/*contracts.md`。
* 仓库已有高层真相文档：`docs/PRD.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`、`docs/STATUS.md`。
* 当前系统是单进程 Python 应用，核心入口为多渠道私聊文本，经 shared private-chat runtime 进入业务链。
* 当前主线能力覆盖：搜索、候选选择、下载确认、状态查询、导入确认、后处理、cleanup、watchlist、成人 BT subscription、多渠道入口。
* 当前项目处于收尾阶段；本轮不应扩功能、不应修改运行时行为。
* 用户已明确指出：主要漂移不在 backend contracts，而在顶层摘要文档仍停留在 T01/T17/T19 之前的旧口径。
* 本轮 docs 收口完成后，用户已明确要求继续修复 3 个既有红灯：`make quality` / `make lint` 的未使用变量，以及 `make verify-mainline` 中 2 条仍断言旧文案的 Telegram 测试。

## Assumptions (temporary)

* `docs/flows/` 继续作为接近代码的 runtime truth，不替代顶层摘要层，但需要被顶层文档明确引用。
* 本轮允许修正顶层文档对审批口径、宿主能力、Telegram-first 交互、渠道能力矩阵和 pure BT 定位的失真描述。
* 本轮允许补 docs gate，专门约束 `docs/STATUS.md` 与 `docs/NEXT_STEP.md` 对最新真实 Telegram smoke 结论的一致性。
* 后续红灯修复应保持行为不变：只去掉无用局部变量，并把测试文案对齐到当前真实输出。

## Open Questions

* 当前无阻塞问题。若后续发现某条顶层文档需要重写的范围超过“摘要层纠偏”，再单独收敛范围。

## Requirements (evolving)

* 文档必须基于当前真实代码，而不是只复述现有 PRD/ARCHITECTURE。
* `docs/flows/` 继续覆盖：
  * 启动装配与 sidecar 生命周期
  * 多渠道入口到 shared runtime 的统一路径
  * 搜索 -> 候选 -> 下载确认 -> 下载状态 -> 自动导入/成人归档
  * 手动导入与 copy-fallback
  * cleanup guardrail
  * direct BT / adult BT / pure BT 分支
  * watchlist 与 `btsub` 的运行方式
  * 持久化真相表与关键事件节点
* 顶层文档必须对齐这些 runtime truth，至少修正：
  * 审批口径：`direct source` / BT follow-up / duplicate override / copy-fallback 仍需显式 `confirm`；数字选资源和 `import <ref>` 是 guarded auto-confirm。
  * 启动画像：`load_settings()` 是 capability-based fail-closed；Telegram / WeCom / Feishu 宿主判定不能再写成 Telegram-only。
  * 交互画像：Telegram-first 已进入按钮 / callback 主链，不能再写成“私聊文本是唯一主交互面”。
  * 渠道能力：shared runtime 统一不等于主动通知能力对称，WeCom 主动发送当前 unsupported。
  * pure BT：文档必须明确它是“代码保留、提示收起”的兼容分支，而不是与 PT / 成人 BT 同权的用户主链。
* `docs/INDEX.md` 需要把 `docs/flows/` 纳入 AI / 开发者阅读路径。
* `docs/SEARCH_REPLY_PRESENTATION_PLAN.md` 需要被标记为 superseded 或归档，避免与已交付 Telegram-first 行为相冲突。
* 文档收口完成后，允许做 2 个最小代码/测试修复：
  * 删除 `app/bot/telegram_update_runtime.py` 中未使用的 `task_identity` 局部变量，恢复 `make lint` / `make quality`
  * 将 `tests/test_telegram_bot.py` 中 2 条旧断言从“等待下载器首次同步”对齐到当前真实文案“等待下载器同步”，恢复 `make verify-mainline`
* 不新增运行依赖，不借机改业务逻辑，不扩大到其他无关测试或重构。

## Acceptance Criteria (evolving)

* [ ] `docs/flows/` 下存在基于真实代码整理的流程文档集合，并被 `docs/INDEX.md` 暴露给 AI / 开发者阅读路径。
* [ ] `docs/PRD.md`、`docs/ARCHITECTURE.md`、`docs/NEXT_STEP.md`、`docs/STATUS.md` 对当前代码和 `docs/flows/` 没有明显冲突。
* [ ] 顶层文档已明确 guarded auto-confirm、capability-based host、Telegram-first callback 主链、渠道能力矩阵和 pure BT 兼容分支定位。
* [ ] docs gate 新增至少一条跨文档一致性检查，用来约束最新真实 Telegram smoke 结论不打架。
* [ ] `app/bot/telegram_update_runtime.py` 的未使用变量红灯已移除。
* [ ] `tests/test_telegram_bot.py` 的 2 条 Telegram add-success 断言已与真实输出对齐。
* [ ] `make quality`、`make lint`、`make verify-mainline` 通过，且不通过的话必须能明确归因到本轮范围之外的问题。

## Definition of Done (team quality bar)

* 文档落盘并可导航
* 顶层摘要层与 runtime truth 对齐
* 相关文档引用和目录结构保持清晰
* 已做最小必要的一致性检查
* 明确记录本轮仅为文档纠偏与 gate 补强，不宣称新增实现

## Out of Scope (explicit)

* 任何业务逻辑、配置能力、依赖、架构边界的修改
* 新功能设计或产品重定义
* 为了“写得更完整”而把顶层摘要文档膨胀成逐函数说明
* 借修红灯顺手改 Telegram 交付语义、下载状态文案或运行时行为
* 自动发布、push 或提交

## Technical Notes

* 入口真相来源优先级：代码 > `.trellis/spec/backend/*contracts.md` > `docs/flows/` > `docs/DECISIONS.md` / `docs/ARCHITECTURE.md` / `docs/STATUS.md`
* 重点代码入口预计包括：
  * `app/main.py`
  * `app/bot/private_chat_runtime.py`
  * `app/bot/private_chat_bt_*`
  * `app/services/*.py`
  * `app/db/*.py`
  * `app/runtime/*.py`
* 重点漂移点包括：
  * `app/bot/private_chat_selection_runtime.py`
  * `app/bot/private_chat_import_runtime.py`
  * `app/services/import_to_library.py`
  * `app/config.py`
  * `app/bot/telegram_runtime_adapter.py`
  * `app/bot/shared_private_chat_sender.py`
  * `app/bot/bt_processing_path_runtime.py`
  * `app/bot/query_text_runtime.py`
* 收尾红灯修复触点仅限：
  * `app/bot/telegram_update_runtime.py`
  * `tests/test_telegram_bot.py`
* 输出形式倾向于“flows truth + 顶层摘要纠偏 + docs gate 补强 + 最小红灯修复”。
