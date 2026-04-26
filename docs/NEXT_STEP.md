# Next step (v361)

## Current goal

- 当前唯一主线切到 **验证入口收口 / 操作文档瘦身**。
- 这一轮只服务两件事：
  - 收 `Makefile` 的公开验证入口，优先是 `verify-mainline` 和 cleanup targets
  - 收 `docs/OPERATOR_RUNBOOK.md` 这类操作者入口文档，去掉过时主线残留和重复说明
- 已完成态保持，不回退：
  - 成人 BT 站点优先、历史账本、只读补全、归档与保留期清理
  - 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态
  - `search_media.py` 当前 `627` 行，BT 只读展示逻辑已抽到 `app/services/bt_read_only_display.py`
  - `import_to_library.py` 当前 `590` 行，confirmed media identity 回查已抽到 `app/services/import_confirmed_media_identity.py`
  - `app/bot/private_chat_runtime.py` 当前 `476` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退
- 这条主线的详细蓝图统一看 `docs/VERIFICATION_ENTRYPOINTS_PLAN.md`。

## User value

- 非技术操作者下一线程能直接照文档推进，不再先花时间判断“该跑哪条 make 命令 / 哪条 prompt 还没过时”。
- 验证入口收口后，仓库会更容易看清“测试真的健康，还是只是入口碎片很多”。
- 这一步不碰 approval / lease / confirm / recovery 真相边界，避免为了“文档变短”把副作用安全一起削掉。

## Only do

- 只做 `Makefile` 公开验证入口收口：
  - `verify-mainline` 从碎片命令堆收成少数几个分组 target 再汇总
  - cleanup 公开 target 收到少数几个操作者真正需要的入口
- 只做操作者文档瘦身：
  - `docs/OPERATOR_RUNBOOK.md`
  - 按需补 `docs/STATUS.md`、`docs/INDEX.md`
- 继续保持当前搜索 / 导入 / 成人 BT 已收口代码真相与文档一致。

## Do not do

- 不把 `verify-mainline` 直接粗暴改成单条 `pytest tests/ -q`。
- 不在这一步删除 approval / lease / version / confirm / recovery 协议。
- 不在这一步动业务代码、交互协议、SQLite 真相边界。
- 不顺手扩到 `.env.example`、`AGENTS.md` 或消息展示体验层实现。

## Done when

当前这条 **验证入口收口 / 操作文档瘦身** 主线满足：

1. `Makefile` 的公开验证入口明显收口，`verify-mainline` 和 cleanup target 不再是操作者层面的碎片命令堆。
2. `docs/OPERATOR_RUNBOOK.md` 不再引用旧主线或过时 plan，默认模板只服务当前主线。
3. `docs/STATUS.md`、`docs/NEXT_STEP.md`、`docs/OPERATOR_RUNBOOK.md` 对“下一线程该做什么”表述一致。
4. `tests/test_cleanup_docs_consistency.py` 和这轮涉及的 Makefile / docs gate 都已通过。

## After this step

1. 如果验证入口和操作文档都收口，再切回代码热点，优先看 `add_to_downloader.py`。
2. 如果后续仍想继续压文档/配置负担，再单开 `AGENTS.md` / `.env.example` 入口瘦身主线，不和这一步混做。
