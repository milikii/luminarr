# brainstorm: telegram real smoke restore

## Goal

恢复新的真实 Telegram smoke 证据，覆盖“Telegram 选定 PT 资源后”的后半段真实链路，并把当前真实通知行为与缺口回写到 operator-facing 真相入口。

## What I already know

* 用户这轮想确认的不是“能不能收 Telegram 消息”本身，而是 PT 资源选定后的整条真实链路：
  - 加入下载后会发什么通知
  - 下载状态会不会定时更新
  - 下载完成后会不会通知
  - 自动硬链接到媒体库会不会通知
  - metadata 刮削会不会通知
  - 字幕翻译会不会通知
* `docs/plans/2026-05-02-moviepilot-telegram-pt-resource-interaction.md` 当前只设计到“资源按钮 -> pending approval handoff”，没有覆盖下载完成后的真实观测。
* `docs/plans/2026-05-02-moviepilot-telegram-pt-resource-interaction-test-plan.md` 当前 manual smoke 也只覆盖到“收到现有待确认下载消息”。
* `docs/STATUS.md` / `docs/NEXT_STEP.md` 仍把“新的真实 Telegram smoke 缺失”列为环境侧风险，而不是代码侧缺陷。
* 当前机器上一次环境快照显示：
  - `api.telegram.org` 不可达
  - 没有运行中的 `python -m app.main`
* 当前仓库本地运行前提已具备：
  - `.env` 存在
  - `TELEGRAM_BOT_TOKEN` 已配置
  - `OUTBOUND_PROXY_URL` 已配置
  - `.venv` 存在
* 用户已明确选择本轮范围为：
  - 只做“事实核对型实测”
  - 跑出当前真实通知行为和缺口
  - 补证据与文档
  - 不顺手开发缺失通知能力
* 用户已确认：等本地进程和 Telegram 可达性恢复后，可以手动给 bot 发真实测试消息，补完整的新入站 smoke 证据。
* 代码真相已经确认到以下边界：
  - 资源 `confirm` 后会回复 `已添加下载：...`
  - `status <任务ID或Hash>` 是显式查询动作，不是被动推送
  - 下载完成后台轮询每 `300` 秒跑一次，但当前只会静默刷新 `download_monitor` / 触发 auto-import，不会主动把下载状态消息推给用户
  - auto-import 命中后会生成“导入待确认”消息
  - `confirm import` 成功后会回复导入成功与目标路径，并附带媒体库刷新结果
  - metadata 刮削、字幕翻译会执行并写 job event，但当前不会把成功结果拼回用户回复
* 仓库里没有现成的一键“PT 选种后全链路真实 Telegram smoke”自动化脚本；现有只读证据主要是 focused tests、环境快照和 `logs/trace.log` 历史 trace。

## Assumptions (temporary)

* 这轮最小闭环应该优先走本地 Python 路径，而不是 Docker 路径。
* 这轮需要真实 Telegram 消息进入 bot，不能只靠本地 pytest 或历史 trace 冒充新证据。
* 如果网络问题先于进程问题，就应该先修通 Telegram API 可达性，再起 `app.main`。
* 这轮至少要先把“当前实现真实会通知什么 / 不会通知什么”实测清楚，再决定是否把缺失通知升级成新功能开发。
* 这轮以 Telegram 单通道为准，不把 Feishu / WeCom / personal WeChat 一起纳入实测范围。

## Open Questions

* 当前无阻塞性需求问题；下一阻塞点只可能来自环境恢复本身。

## Requirements (evolving)

* 恢复 `api.telegram.org` 可达性，或至少明确当前代理/网络为何仍然失败。
* 恢复本地 `app.main` 可运行态，并确保 Telegram 宿主链能起来。
* 以真实 Telegram 操作实测 PT 资源选定后的后半段链路：
  - 资源确认下载
  - 下载状态观察
  - 下载完成观察
  - auto-import / import confirm
  - 导入后 metadata / subtitle / refresh
* 产出新的真实 Telegram smoke 证据，而不是只复述历史 trace。
* 将新的环境/证据真相同步回 operator-facing 文档入口。
* 明确记录哪些用户可见通知是“当前就有”，哪些是“后台只有事件/日志，没有用户消息”。
* 若链路卡在环境或人工入站条件，必须明确停在哪一步，不能把 focused tests 伪装成真实 Telegram smoke。

## Acceptance Criteria (evolving)

* [ ] 明确这轮 smoke 验证路径（本地 Python / Docker；Telegram only / multi-channel）。
* [ ] Telegram API 可达性状态已恢复或根因已明确。
* [ ] 本地 `app.main` 成功运行到可接收 Telegram 更新。
* [ ] 至少跑通一次“PT 资源选择 -> confirm 下载 -> 状态/完成观测 -> 导入”真实链路，或明确卡住在哪一段。
* [ ] 对下载、完成、导入、刮削、字幕、刷新各阶段给出“用户看到什么 / 看不到什么”的真实结论。
* [ ] 新证据已记录到 operator-facing 文档入口。

## Definition of Done (team quality bar)

* New evidence is current-session real evidence, not historical trace relabeling
* Relevant docs updated if environment truth changes
* Quality / verification baseline remains green after any code or docs changes

## Out of Scope (explicit)

* 不把历史 trace 重新包装成“新的真实 Telegram smoke”。
* 不默认扩成全渠道统一通知改造。
* 不默认把“当前没有用户通知”的阶段自动视为 bug 并直接开做，除非本轮范围明确升级为功能开发。

## Technical Notes

* Files inspected:
  - `docs/plans/2026-05-02-moviepilot-telegram-pt-resource-interaction.md`
  - `docs/plans/2026-05-02-moviepilot-telegram-pt-resource-interaction-test-plan.md`
  - `docs/STATUS.md`
  - `docs/NEXT_STEP.md`
  - `app/services/add_to_downloader.py`
  - `app/services/get_download_status.py`
  - `app/services/post_download_auto_import.py`
  - `app/services/import_to_library.py`
  - `app/services/import_post_processing.py`
  - `app/services/import_transfer_execution.py`
  - `app/bot/download_follow_up_runtime.py`
