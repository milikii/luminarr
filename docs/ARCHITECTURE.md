# docs/ARCHITECTURE.md (v1)

> 目的：用最直白的方式解释“谁收消息、谁做判断、谁调外部系统、谁写数据库”。

## 1. 系统在做什么

用户在 Telegram / personal WeChat / Feishu / WeCom 私聊里发一句话。

系统做四件事：

1. 渠道适配层把外部消息接进来。
2. shared runtime 把文本解析成明确动作。
3. service 调数据库和外部系统完成动作。
4. 渠道适配层把文本、图片或文件回给原用户。

## 2. 一条消息怎么流动

以 Telegram 里的“`我想看 Dune 2021`”为例：

1. `app/bot/telegram_bot.py` 收到 Telegram update。
2. 渠道层把 Telegram 的 chat/user 映射成内部统一的 `chat_id / user_id`。
3. `app/bot/private_chat_runtime.py` 判断这是 `search_media`，再把参数交给 `app/services/search_media.py`。
4. `search_media.py` 调 TMDB / Prowlarr，拿到候选。
5. `app/db/candidate_repo.py` 把候选写进 SQLite。
6. runtime 组装回复文本。
7. 渠道层把文本发回 Telegram。

同一套 runtime / service / SQLite 真相也被 personal WeChat、Feishu、WeCom 共用。

## 3. 目录怎么分工

| 目录 | 负责什么 | 典型文件 |
| --- | --- | --- |
| `app/main.py` | 启动入口；把 config、repo、client、service、渠道装到一起 | `app/main.py` |
| `app/config.py` | 把环境变量读成 `Settings` | `app/config.py` |
| `app/bot/` | 四个渠道入口 + shared private-chat runtime | `telegram_bot.py`、`personal_wechat_text.py`、`feishu_adapter.py`、`wecom_adapter.py`、`private_chat_runtime.py` |
| `app/services/` | 具体业务动作 | `search_media.py`、`add_to_downloader.py`、`import_to_library.py`、`cleanup_downloaded_source.py` |
| `app/clients/` | 调外部系统的最小协议封装 | `tmdb.py`、`prowlarr.py`、`transmission.py`、`qbittorrent.py`、`emby.py` |
| `app/db/` | SQLite 真相层 | `sqlite.py`、`job_repo.py`、`job_event_repo.py`、`approval_repo.py` |
| `app/runtime/` | 运行时规则、执行边界 | `execution_policy.py` |
| `tests/` | 行为回归和协议保护 | `test_cleanup_cross_channel_smoke.py`、`test_import_to_library.py` 等 |

## 4. SQLite 在这里做什么

SQLite 是当前唯一真相源。下面这些状态都落在 SQLite：

- `jobs`：当前任务是谁、归谁执行、lease/version 是什么。
- `job_event`：这条任务已经发生了什么，比如 `import.succeeded`、`cleanup.failed`。
- `approval_record`：哪些动作还在等 `confirm`。
- `candidate_mapping`：搜索候选和序号映射。
- `watchlist` / `bt_subscription`：用户持久化关注内容。

外部系统不是账本：

- TMDB / Fanart：提供元数据。
- Prowlarr / WebSource：提供搜索候选。
- Transmission / qBittorrent：提供下载动作和状态。
- Emby：提供刷新动作。

## 5. 几条主链

### 搜索到下载

`用户文本 -> private_chat_runtime -> search_media -> candidate_repo -> add_to_downloader -> approval_repo -> confirm -> 下载器 client`

### 下载完成到入库

`下载状态 -> post_download_auto_import -> import_to_library -> job_event(import.succeeded) -> metadata_scraper -> subtitle_translator -> refresh_media_server`

### cleanup

`cleanup 文本 -> cleanup_downloaded_source -> job_event 查 import 关联 -> 只读预检或删除源文件 -> job_event 写 cleanup 结果 -> 文本回用户`

### watchlist / btsub

`用户文本 -> runtime -> manage_watchlist / manage_bt_subscription -> SQLite 持久化 -> 后台 tick 或手动命令再进入既有 downloader approval 边界`

## 6. 四个渠道为什么没有分叉成四套业务代码

因为渠道层只处理“协议差异”，不处理“业务真相”。

渠道层负责：

- 验签、解密、长轮询或 webhook 收包。
- 把外部会话标识投影成内部 `chat_id / user_id`。
- 调 shared runtime。
- 把文本、图片或文件发回去。

业务层负责：

- 解析动作。
- 查 SQLite。
- 调外部系统。
- 生成回复内容。

所以同一个 cleanup / import / search 协议，不会在四个渠道里各写一份。

## 7. 现在最容易读懂的入口

如果你想快速理解这个仓库，建议按下面顺序看代码：

1. `app/main.py`
2. `app/config.py`
3. `app/bot/private_chat_runtime.py`
4. `app/services/search_media.py`
5. `app/services/add_to_downloader.py`
6. `app/services/import_to_library.py`
7. `app/services/cleanup_downloaded_source.py`
8. `app/db/job_repo.py` 和 `app/db/job_event_repo.py`

## 8. 当前不做什么

- 现在不把 `app/` 目录重命名成更花哨的层级。
- 现在不把四渠道抽成通用平台。
- 现在不引入 Web UI、Redis、PostgreSQL、多机部署。

原因很简单：当前瓶颈是知识入口和施工协作，不是代码目录名。
