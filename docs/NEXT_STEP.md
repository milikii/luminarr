# Next step (v362)

## Current goal

- 当前唯一主线切到 **`search_media.py` ambiguity / media-BT 排序 / batch preview helper 收口 / 质量硬化**。
- 这一轮只服务两件事：
  - 收 `app/services/search_media.py` 里仍堆在主文件里的歧义澄清 helper、media-BT 排序回退 helper、batch preview 页面支持 helper
  - 保持刚完成的 downloader adult registry helper 收口和公开验证入口收口完成态，不回退
- 已完成态保持，不回退：
  - `Makefile` 公开验证入口已收口：`verify-mainline` 当前改成 4 个分组 target 汇总入口，cleanup 公开入口当前收敛到 `test-cleanup-smoke` / `test-cleanup` / `test-cleanup-docs-gate` / `test-cleanup-window`
  - `docs/OPERATOR_RUNBOOK.md` / `docs/GETTING_STARTED.md` 当前已去掉过时主线残留和重复入口
  - 成人 BT 站点优先、历史账本、只读补全、归档与保留期清理
  - 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态
  - `app/services/add_adult_registry_state.py` 已承接 adult pending / downloading 状态写入；`add_to_downloader.py` 当前 `582` 行，只剩 proof-like wrapper
  - `search_media.py` 当前 `628` 行，BT 只读展示逻辑已抽到 `app/services/bt_read_only_display.py`
  - `import_to_library.py` 当前 `590` 行，confirmed media identity 回查已抽到 `app/services/import_confirmed_media_identity.py`
  - `app/bot/private_chat_runtime.py` 当前 `476` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退
  - 这条主线的详细蓝图统一看 `docs/SEARCH_MEDIA_SLIMMING_LOG.md`。

## User value

- 继续把搜索热点文件里的稳定 helper 抽走，后续再修 ambiguity、电影 BT 排序和批量预览页面支持时，不会继续把所有小改动堆回 `search_media.py`。
- 这一步只动 helper / 壳层和 focused tests，不碰 candidate / clarification / BT helper truth、shared runtime、下载确认或导入协议边界。
- downloader confirm 主线已经收口到可停手状态，这一步把精力切回当前最大的剩余热点文件。

## Only do

- 只收 `search_media.py` 当前仍直连的稳定 helper：
  - ambiguity / 澄清文案判定
  - media-BT 排序 / fallback query 推导 / 去重
  - batch preview 页面支持 / allowlist URL fetch 壳
- 每轮只做一个最小闭环；同步补对应 focused tests、`docs/STATUS.md`、`docs/NEXT_STEP.md` 和 `docs/SEARCH_MEDIA_SLIMMING_LOG.md`。
- 继续保持当前 downloader / 导入 / 成人 BT / 验证入口已收口真相与文档一致。

## Do not do

- 不为降行数而继续机械拆 helper；只有稳定职责边界才允许抽走。
- 不在这一步改 clarification / candidate / BT helper truth、shared runtime、下载确认 / 导入协议或新的入口文档设计。
- 不在这一步切回 `add_to_downloader.py` / `import_to_library.py` confirm 主体，或顺手扩展消息展示体验层。
- 不顺手扩到 `.env.example`、`AGENTS.md` 或新的 operator prompt 设计。

## Done when

当前这条 **`search_media.py` ambiguity / media-BT 排序 / batch preview helper 收口 / 质量硬化** 主线满足：

1. `search_media.py` 至少再抽走一组稳定 helper 职责，或让主文件对 ambiguity / 排序 / batch preview 的职责明显更单一。
2. `tests/test_search_media.py` 的相关 focused gate 与这轮涉及的质量 gate 均通过。
3. `docs/STATUS.md`、`docs/NEXT_STEP.md`、`docs/SEARCH_MEDIA_SLIMMING_LOG.md` 对当前风险和下一线程表述一致。

## After this step

1. 如果 `search_media.py` 再收几轮后只剩 proof-like wrapper，再评估是否切去 `import_to_library.py` 或新的消息展示热点。
2. 如果后续仍想继续压文档/配置负担，再单开 `AGENTS.md` / `.env.example` 入口瘦身主线，不和搜索主线混做。
