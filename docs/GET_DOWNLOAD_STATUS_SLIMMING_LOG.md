# docs/GET_DOWNLOAD_STATUS_SLIMMING_LOG.md (v1)

> 目的：承接当前“`get_download_status.py` 状态编排层瘦身 / 模块化”主线的详细台账。

## 1. Current line

- 当前主线状态：`get_download_status.py` 状态编排层瘦身 / 模块化进行中。
- 上一条已完成主线 **BT 方向剩余用户价值重评估** 已在 2026-04-20 冷启动审计中满足 `Done when` 第 2 条：继续留在 BT proof 家族里只会重复命中同一个下载器可达性缺口，没有新增副作用真相、协议能力或结构降本，因此当前已按 `After this step` 第 1 项切到结构降本主线。
- 当前文件同时承接三类事情：`status <任务ID/Hash>` 查询编排、`download_monitor + job_event + auto-import` 跟进、副作用完成后给四渠道渲染状态回复；当前主线的目标不是改协议，而是把这三段责任拆清楚。

## 2. Risk groups

### 2.1 查询编排 / 下载器状态读取

- 保持 `parse_status_query()`、`GetDownloadStatusService.get_status_text()` 的命令协议和失败文本不回退。
- 保持下载器查询失败时的显式中文红色日志、`STATUS_QUERY_FAILED_TEXT` 与 `STATUS_NOT_FOUND_TEXT` 不变。

### 2.2 观察落盘 / 完成事件 / 自动导入跟进

- 保持 `download_monitor.record_status()`、`downloader.completed_observed` 事件追加、`post_download_auto_import_service.run_for_record()` 的调用顺序不变。
- 保持结果缺失 / 记录损坏 / SQLite 异常三类中文日志与 warning 文本不回退。

### 2.3 四渠道状态展示 / DeliveryItem 渲染

- 保持 Telegram / personal WeChat / Feishu / WeCom 继续共用同一套 `DeliveryItem` 渲染边界。
- 保持非交付渠道继续返回原有纯文本状态，字段顺序、进度/速度/ETA 文本不回退。

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_get_download_status.py -k "parse_status_query or get_status_text_success or personal_wechat_channel or render_status_reply"`
- `.venv/bin/python -m pytest -q tests/test_get_download_status.py -k "download_monitor or completion_event or auto_import_terminal or skip_event"`
- `.venv/bin/python -m pytest -q tests/test_private_chat_runtime.py tests/test_telegram_bot.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py -k "status"`

## 4. Maintenance rule

- 新闭环优先继续并到这份台账的现有风险分组，不新开按日期拆的小节。
- 若某次施工只是在同一个 helper 上补一条 `< 20 行` 的 `if/elif/log` 诊断分支，且上一轮也是同类微闭环，就按 `AGENTS.md §11` 触发诊断分流递减停机。
