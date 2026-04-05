# Current status (v99)

## Project position

Luminarr 当前是一个同时服务 **Telegram + personal WeChat + Feishu + WeCom** 四个私聊入口的垂直影视自动化 Harness。

当前固定主线：
- Telegram + personal WeChat + Feishu + WeCom（最小私聊文本基线）
- TMDB
- Prowlarr（当前主来源）+ 最小 BT WebSource（仅 BT 使用）
- Transmission + qBittorrent
- Emby
- SQLite
- Docker Compose
- 单实例 / 单进程 / 单机
- movie-first

## What is implemented now

- 控制层：
  - `shared private-chat text runtime`
  - Telegram runtime + 最小图片/文件发送 + 搜索结果/下载审批/导入审批文本 polish
  - personal WeChat 二维码登录入口 + 单账号私聊文本轮询
  - Feishu 私聊文本 webhook + 文本回消息 + 事件验签
  - WeCom callback URL 校验 + 验签解密入站 + 加密被动文本回包
  - four-channel cleanup smoke regression gate baseline（`tests/test_cleanup_cross_channel_smoke.py` 当前会用 Telegram / personal WeChat / Feishu / WeCom 四个公开入口聚合验证英文/中文 bare `cleanup` / bare `cleanup inspect` discoverability、英文/中文原始 `task_id` 与 `task_hash` 的 `cleanup inspect` / `cleanup` 执行烟测、英文/中文 `target missing` rejection guidance 烟测，以及英文/中文 `chat-scoped task_ref -> jobs -> import correlation` 烟测，不改业务协议）
  - cleanup verification docs consistency gate baseline（`tests/test_cleanup_docs_consistency.py` 当前会校验 `docs/NEXT_STEP.md`、`docs/STATUS.md`、`docs/CLEANUP_VERIFICATION_WINDOW.md` 在验证窗口日期、聚合 smoke gate、`当前结论`、真实私聊 smoke 提示与 `chat-scoped task_ref -> jobs -> import correlation` 描述上保持一致，避免窗口台账和快照文档漂移）
  - `telegram_updates` 去重
  - `jobs.version + lease_owner + lease_until` 执行所有权
  - downloader / import approval、approval timeout、confirm wake rebuild、clarification durable truth、read-only concurrency-safe execution policy
- 媒体主链：
  - `search_media`、TMDB-first 搜索、候选映射持久化
  - downloader approval / `confirm` / dispatch / `status`
  - import approval / `confirm` / hardlink import
  - cross-filesystem copy-fallback approval
  - completion-monitor + post-download auto import
  - downloader/library asset correlation
  - downloader/library cleanup 最小闭环：
    - `cleanup inspect`
    - `cleanup`
    - discoverability
    - rejection guidance
    - success follow-up
    - failure observability（删除失败、关联查询失败、任务解析失败、事件落盘失败，以及 cleanup 执行被 correlation 缺失 / target 缺失 / source 已不存在 / guard 拒绝阻断时，都会打印显式中文日志和处理建议）
    - chat-scoped `task_ref` 解析
  - filename normalization
  - metadata scraping（TMDB + Fanart.tv）
  - subtitle auto-translation（当前仅 `.srt`）
  - Emby refresh
- BT 主链：
  - PT / BT parser-level split
  - 原始磁力 processing-path inquiry（`影视入库链 / 纯 BT 下载链`）
  - BT classification（`movie / series / anime / raw_bt`）
  - BT `movie / series / anime` TMDB association
  - `raw_bt` destination selection
  - BT shared source adapter（`Prowlarr + WebSource`）
  - pure BT single-item ranking
  - BT external web-source baseline
  - BT WebSource richer metadata extraction baseline（当前内建 `nyaa` 已补 `size + seeders`）
  - BT-only read-only helper（`bt搜 <关键词>` / `bt search <关键词>`）
  - downloader role binding
  - Transmission + qBittorrent 最小协议执行
  - `manage_bt_subscription`：`list/add/remove/clear/run` + scheduler tick + deterministic candidate-selection
- 其他：
  - `manage_watchlist` 手动持久化基线
  - `watchlist` 的 `movie / series / anime` 分类真相

## Current focus

- 当前主线不是继续扩 cleanup，而是把 cleanup 收口成一个有退出条件的四渠道验证窗口。
- 当前验证目标是：四个渠道都要真实可用，但业务真相仍只维护在 shared runtime、workflow、approval、`jobs` 和 SQLite 一套边界里。
- `docs/CLEANUP_VERIFICATION_WINDOW.md` 已作为当前验证窗口台账落地；窗口开始日期固定为 2026-04-05，最早可结束日期固定为 2026-04-12。
- 验证窗口台账当前会显式写出“当前结论”，说明是否已满足退出条件，避免只看状态或只看勾选项。
- 当前四个渠道的真实私聊 smoke 记录仍全部待补；`docs/STATUS.md` 只保留快照，逐项证据写入 `docs/CLEANUP_VERIFICATION_WINDOW.md`。

## Main risks and gaps

- `series / anime` 独立名称解析还没实现；当前最稳的是 movie-first。
- 四个渠道都在真用，最大的维护风险是渠道适配层和 shared runtime 漂移，导致同一协议在四处长出不同分支。
- personal WeChat 当前只支持单账号、私聊文本；同一进程里刚完成 `微信登录` 后，要到下一次启动才会开始轮询。
- Feishu / WeCom 当前只支持最小私聊文本，不支持群聊、图片、卡片、按钮回调；WeCom 也还没有主动发消息客户端。
- cleanup inspect / execution 当前只对带结构化 `source_path + target_path` 的导入任务可用；更早历史任务仍需人工甄别。
- completion truth 仍主要依赖当前 runtime 观察，不是完整独立后台轮询平台。
- metadata scraping、subtitle auto-translation、Emby refresh 失败时不会回滚 import success；缺配置时会显式失败。
- BT shared source adapter、BT external web-source、pure BT ranking、`btsub` 选源都已可用，但还不是共享确定性评分器。

## Latest verification

- tests：`417 passed, 2 skipped`（`.venv/bin/python -m pytest -q`）
- four-channel cleanup smoke tests：`72 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）
- cleanup service tests：`25 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py`）
- focused cleanup tests：`167 passed, 91 deselected`（`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup`）
- cleanup verification window doc check：`74 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py`）
- compile check：`passed`（`python3 -m compileall app tests`）
- docs consistency check：`passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`）
- manual verification：
  - downloader/library cleanup execution baseline passed（`.venv/bin/python tmp_tests/verify_cleanup_execution_baseline.py`）
  - qBittorrent protocol baseline passed
  - BT subscription baseline passed
  - BT subscription scheduler-tick baseline passed
  - BT subscription deterministic candidate-selection baseline passed
  - original magnet processing-path inquiry baseline passed
  - pure BT single-item ranking baseline passed
  - BT external web-source baseline passed
  - BT WebSource richer metadata extraction baseline passed
  - BT-only read-only helper baseline passed

## Current priority

- 在四渠道都可用的前提下，继续完成 cleanup 的 7 天验证窗口，并保持 `tests/test_cleanup_cross_channel_smoke.py` 这条聚合 smoke gate（含英文/中文 discoverability、inspect、execution、target-missing rejection guidance 与 `chat-scoped task_ref -> jobs -> import correlation` 路径）稳定；若出现问题，只修 shared runtime、渠道胶水或显式日志，不扩自动 cleanup、批量 cleanup 或删种。
- 当前窗口证据统一落在 `docs/CLEANUP_VERIFICATION_WINDOW.md`；完成真实私聊 smoke 后，只更新这份台账和 `docs/STATUS.md` 快照，不新增 cleanup 协议或额外工作流。
- 台账里的 `当前状态`、`当前结论`、退出清单和四渠道进度必须相互一致，不能出现“状态已完成但渠道仍待验证”这类漂移。
