# Next step (v288)

## Current goal

- 当前质量硬化阶段的下一条最小主线切到 **`private_chat_runtime.py` 的 execution-gated shared route block 边界瘦身**。
- 刚完成的上一条主线是 **`private_chat_runtime.py` 的 downloader execution lambda helper 边界瘦身**：BT / PT 的 downloader execution 透传已收成局部 shared resolver，不再在 4 个路由点各自内联 lambda，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 runtime bootstrap helper 边界瘦身**：主函数开头的 `tg / execution_gate / traced reply` 装配已抽到 `_prepare_private_chat_runtime_bootstrap()`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 BT pending 预检 helper 边界瘦身**：BT processing / classification follow-up 前的 query 解析、pending 读取和 service-not-ready 早退已抽到 `_resolve_bt_follow_up_precheck()`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 dispatch wrapper 边界瘦身**：`dispatch_private_chat_text()` 已从 shared runtime 主文件移除，Telegram / Feishu / WeCom / personal WeChat 入口和相关 tests 已直接 alias 到 `handle_private_chat_query_text()`，当前不回退。
- 再上一条主线是 **`telegram_bot.py` 的剩余纯 wrapper 清零**：`build_application()` 与无调用点的 `handle_private_chat_query_text()` 已从主文件移除，应用构建入口已直接复用 `telegram_runtime_adapter.py`，当前不回退。
- 再上一条主线是 **`telegram_bot.py` 的 Telegram entry wrapper 边界瘦身**：`handle_message()` / `handle_callback_query()` 已从主文件移除，`telegram_runtime_adapter.py` 已直接挂自己的 message / callback 入口，tests 也已直接复用 runtime adapter 入口，当前不回退。
- 再上一条主线是 **`telegram_bot.py` 的 delivery / formatter 薄包装收口**：`build_telegram_send_media_func()` / `build_telegram_send_text_func()` / `_format_telegram_reply()` 已从主文件移除，`telegram_runtime_adapter.py` 与 tests 已直接复用 `telegram_delivery_runtime.py` / `telegram_reply_formatter.py`，当前不回退。
- 再上一条主线是 **`telegram_bot.py` 的 download follow-up wrapper 边界瘦身**：`_post_download_auto_import_scheduler_loop()` / `_poll_pending_download_completion_once()` / `_download_completion_polling_loop()` 已从主文件移除，download follow-up 调度只保留在 `app/bot/download_follow_up_runtime.py`，当前不回退。
- 再上一条主线是 **`telegram_bot.py` 的 BT entry helper 边界瘦身**：`_enter_pure_bt_flow()` / `_enter_media_import_bt_flow()` 已抽到 `app/bot/telegram_bt_entry_runtime.py`，`verify-mainline` 已补进 Telegram BT entry focused tests，当前不回退。
- 再上一条主线是 **`telegram_bot.py` 的 BT follow-up helper 死代码收口**：raw BT destination / BT TMDB follow-up 的 Telegram 死包装已从主文件移除，shared runtime 不再保留无调用点兼容层，当前不回退。
- 再上一条主线是 **`telegram_bot.py` 的 BT pending helper 边界瘦身**：processing-path / classification / TMDB association / raw destination 的 pending 上下文包装已抽到 `app/bot/telegram_bt_pending_runtime.py`，`verify-mainline` 已补进 Telegram pending focused tests，当前不回退。
- 再上一条主线是 **`telegram_bot.py` 的 bound downloader execution helper 边界瘦身**：downloader role binding / 实例解析上下文包装已抽到 `app/bot/telegram_downloader_execution_runtime.py`，`verify-mainline` 已补进 Telegram downloader execution focused tests，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 bound downloader execution resolver helper 边界瘦身**：downloader role binding / 实例解析已抽到 `app/bot/private_chat_downloader_execution_runtime.py`，confirm / digit-selection 薄包装已从主文件移除，并把 resolver focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 raw BT destination follow-up helper 边界瘦身**：raw BT pending 读取、clear 回调、downloader execution 透传和 reply 回传已抽到 `app/bot/private_chat_raw_bt_destination_runtime.py`，并把 raw BT destination focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 BT TMDB follow-up helper 边界瘦身**：TMDB pending 读取、候选 lookup 绑定、downloader execution 透传和 reply 回传已抽到 `app/bot/private_chat_bt_tmdb_runtime.py`，并把 BT TMDB focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 BT classification follow-up helper 边界瘦身**：classification pending 读取、冲突态清理和 media-import reply 已抽到 `app/bot/private_chat_bt_classification_runtime.py`，并把 BT classification focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 BT processing-path follow-up helper 边界瘦身**：pending source 读取、冲突态清理和 media-import / pure-BT reply 组装已抽到 `app/bot/private_chat_bt_processing_runtime.py`，并把 BT processing focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 BT direct-intent pending reset helper 边界瘦身**：磁力 / 直接 BT 入口的 pending 清理与 processing-path 待处理写入已抽到 `app/bot/private_chat_bt_direct_runtime.py`，并把 BT direct focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 frustration cancel / reset helper 边界瘦身**：取消路由里的 service/repo 分流、执行 gate 和 BT pending 清理已抽到 `app/bot/private_chat_frustration_runtime.py`，并把 frustration focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 BT batch confirm 执行 helper 边界瘦身**：query 解析、格式校验、downloader 绑定解析和执行 gate 已抽到 `app/bot/private_chat_bt_batch_confirm_runtime.py`，并把 BT batch confirm focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 BT read-only helper / batch preview 路由边界瘦身**：query 解析、执行 gate 和失败日志已抽到 `app/bot/private_chat_bt_read_only_runtime.py`，并把 BT read-only focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 search fallback 路由边界瘦身**：search fallback 和 BT 待处理提醒已抽到 `app/bot/private_chat_search_runtime.py`，并把 search focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 cleanup 路由边界瘦身**：cleanup 路由已抽到 `app/bot/private_chat_cleanup_runtime.py`，并把 cleanup focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 BT subscription 路由边界瘦身**：BT subscription 路由已抽到 `app/bot/private_chat_bt_subscription_runtime.py`，并把 subscription focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 watchlist 路由边界瘦身**：watchlist 路由已抽到 `app/bot/private_chat_watchlist_runtime.py`，并把 watchlist focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 import 路由边界瘦身**：import 路由已抽到 `app/bot/private_chat_import_runtime.py`，并把 import focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的状态查询路由边界瘦身**：状态查询路由已抽到 `app/bot/private_chat_status_runtime.py`，并把 status focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 personal WeChat 登录路由边界瘦身**：登录路由已抽到 `app/bot/private_chat_login_runtime.py`，并把 personal WeChat 登录 focused tests 补进 `verify-mainline`，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 trace 包装边界瘦身**：trace 路径解析、入站日志和 reply trace 包装已抽到 `app/bot/private_chat_trace_runtime.py`，`verify-mainline` 已补进 trace focused tests，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 digit-selection 路由边界瘦身**：澄清态判断、下载器解析和 add 调度已抽到 `app/bot/private_chat_selection_runtime.py`，并补了 digit focused tests，当前不回退。
- 再上一条主线是 **`private_chat_runtime.py` 的 confirm 路由边界瘦身**：job 关联查询、workflow 分流和 pending add fallback 已抽到 `app/bot/private_chat_confirm_runtime.py`，并补了 confirm focused tests，当前不回退。
- 再上一条主线是 **Telegram 发送 helper 边界瘦身**：媒资发送、文本发送和 Telegram 图片/文件判定已抽到 `app/bot/telegram_delivery_runtime.py`，`telegram_runtime_adapter.py` 已直接复用这层发送出口，当前不回退。
- 再上一条主线是 **Telegram reply formatter 边界瘦身**：搜索卡片、下载审批、导入审批三段 Telegram 特有文本整形已抽到 `app/bot/telegram_reply_formatter.py`，当前不回退。
- 再上一条主线是 **Telegram 生命周期编排边界瘦身**：sidecar 启停、Application lifecycle 入口、BT scheduler loop / 日志 / downloader resolution 都已收进 `app/bot/telegram_sidecar_runtime.py`，当前不回退。
- `app/bot/telegram_bot.py` 已降到 `256` 行，仅保留 BT 兼容常量与 `_format_bt_classification_result()`；`app/bot/private_chat_runtime.py` 当前为 `359` 行，runtime bootstrap 与 downloader execution lambda 已收口，但 status / watchlist / BT subscription / import / cleanup 这一段 execution-gated shared route 仍直接堆在主函数中。
- 上一条已完成主线是 **`Makefile` / `verify-mainline` 补齐 download follow-up runtime 的固定质量入口**：`app/bot/download_follow_up_runtime.py` focused tests 已纳入固定回归，当前不回退。
- 再上一条已完成主线是 **`telegram_bot.py` 里的 `post_download_auto_import` / `download_completion_polling` 调度边界瘦身**：下载完成轮询与自动导入调度已抽到 `app/bot/download_follow_up_runtime.py`，当前不回退。
- 再上一条已完成主线是 **`app/bot/telegram_runtime_adapter.py` 的 message / callback 入口边界收口**：Telegram message / callback 入口共用的 chat/user 解析、去重落盘和 reply 包装已抽到 `app/bot/telegram_update_runtime.py`，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT TMDB / raw_bt follow-up 与 pending reminder 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT processing-path / classification follow-up 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 frustration / reset 路由分支瘦身**，当前不回退。
- 再上一条已完成主线是 **`private_chat_runtime.py` 里的 BT 直接入口 pending 初始化分支瘦身**，当前不回退。
- 更早一条已完成主线是 **`private_chat_runtime.py` 里的 BT 批量确认路由分支瘦身**，当前不回退。
- 更早一条已完成主线是 **`private_chat_runtime.py` 里的 BT 只读探索 / cleanup 路由分支瘦身**，当前不回退。
- 更早一条已完成主线 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态，不回退。
- `telegram_bot.py` 纯 wrapper 已基本清空，当前更小也更直接的下一步，是继续留在 `private_chat_runtime.py` 收掉中段连续的 execution-gated shared route block，避免 shared runtime 主函数继续背一长段相同上下文的路由透传。
- 这一步继续只做最小边界瘦身，不顺手放大成新的搜索平台、统一回复总线或大文件总重写。
- 质量基线前置条件已满足：默认分支本轮复验 `.venv/bin/python -m pytest -q` 为 `1714 passed, 2 skipped`。

## User value

- 在 runtime bootstrap 和 downloader execution lambda 都已收口后，继续收 `private_chat_runtime.py` 中段连续的 execution-gated shared route block，可以让主函数进一步靠近“只做路由编排”。
- 在默认分支已经稳绿、固定 gate 已补齐的前提下，优先继续降低热点文件体积和 shared runtime/service 耦合。
- 避免 shared runtime 主函数继续手写一长段重复的 `query / bot_data / execution_gate / reply_func / chat_id / tg` 路由透传细节。

## Only do

- 只做一次保守瘦身：围绕 `private_chat_runtime.py` 中段 execution-gated shared route block 做最小 helper 收口。
- 保持现有 parser / routing / approval / SQLite 真相边界不变，不新增用户可感知功能，不改渠道外部协议。
- 保持当前 download follow-up 调度、错误文案和中文日志语义不回退。
- 文档继续分层：`STATUS.md` 只写当前快照；`NEXT_STEP.md` 只写当前唯一主线。

## Do not do

- 不放宽 approval、`jobs` / `job_event` / lease/version / SQLite 真相边界。
- 不新增功能、不扩协议、不顺手重写整个 `telegram_bot.py` / `private_chat_runtime.py`。
- 不把 Telegram 渠道调度段直接平台化成新的全局 scheduler 抽象。
- 不改处理链提示协议、BT pending / approval / SQLite 真相边界。
- 不调整 `confirm` / `select` 文本协议，不改 pending add / pending import / candidate mapping / trace 日志内容语义。
- 不把 Feishu/WeCom webhook、personal WeChat、BT 订阅启动逻辑强行揉成新的“统一 sidecar 平台”。
- 不因为 shared runtime 解耦而把渠道私有 UX 重新散回各渠道各自拼接。
- 不回到 BT 页面 proof、BT dispatch 取证或 Plex 实例追查。

## Done when

当前 **`private_chat_runtime.py` 的 execution-gated shared route block 边界瘦身** 主线视为 **已收口**，满足以下任一条即可：

1. `private_chat_runtime.py` 里至少一段连续的 execution-gated shared route 从主函数抽离，且现有文本语义不变；
2. focused tests 或既有 Telegram / shared runtime 回归能继续覆盖当前 execution-gated route helper 最小回归；
3. 默认分支全量 pytest 继续保持绿灯；
4. 文档继续保持分层一致，`STATUS.md` 只写当前快照，`NEXT_STEP.md` 只写当前唯一主线。

## After this step

1. 如果 `private_chat_runtime.py` 的 execution-gated shared route block 已收口一轮，就继续留在 `private_chat_runtime.py` 选下一条最小瘦身主线，或补对应 focused gate。
2. 如果热点文件暂时没有更小闭环，再继续补 Makefile / focused tests / 真实 smoke 的其他缺口。
3. 只有在 shared runtime 边界和热点大文件都没有更小闭环可做时，才重新考虑次级结构债。
