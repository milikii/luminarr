# State And Event Ledger

> 主要依据：`app/db/sqlite.py`、`app/db/job_repo.py`、`app/db/approval_repo.py`、`app/db/download_monitor_repo.py`、`app/db/job_event_repo.py`

## 1. 为什么这层重要

Luminarr 不是“收到消息马上做完”的脚本。

它的大部分关键动作都依赖三类真相：

- **当前候选 / follow-up 状态**
- **审批与执行状态**
- **事件和观察记录**

如果只看聊天回复，很容易误判系统状态。

## 2. 表分工总表

| 表 | 作用 | 主要写入方 | 主要读取方 |
| --- | --- | --- | --- |
| `candidate_mapping` | 当前 chat 的候选序号映射 | `SearchMediaService` | 数字选片 / 选资源 |
| `clarification_state` | 搜索歧义待澄清 | `SearchMediaService` | 搜索 fallback / 选片保护 |
| `bt_pending_state` | BT follow-up 中间态 | BT runtime | BT follow-up handler |
| `approval_record` | 下载 / 导入审批状态 | add/import service | confirm / stale / expiry 判定 |
| `jobs` | 当前 pending/completed workflow 真相 | add/import service | `confirm` / lease claim / 恢复 |
| `job_event` | 事件流水、source/target 关联 | add/import/status/cleanup/adult | cleanup / 总结 / 调试恢复 |
| `download_monitor` | 下载状态观察与完成观察 | downloader confirm / status polling | status / auto-import / Telegram progress |
| `adult_content_registry` | 成人资源生命周期 | adult add/archive | adult auto-follow-up |
| `adult_duplicate_memory_snapshot` | 成人防重扫描快照 | duplicate memory service | adult duplicate gate |
| `watchlist_item` | 手动想看清单 | watchlist service | watchlist service |
| `bt_subscription_item` | BT 订阅与 last_seen | btsub service | btsub run / scheduler |
| `telegram_updates` | Telegram update 去重 | Telegram adapter | Telegram adapter |

## 3. `approval_record` 和 `jobs` 为什么要同时存在

这两个表解决的是不同问题。

### `approval_record`

负责：

- 这是下载审批还是导入审批
- 当前状态 `pending/approved/cancelled`
- `lease_version`
- `executed_version`
- `expires_at`

它回答的是：

**这次审批在语义上是不是仍然有效。**

### `jobs`

负责：

- 这是哪个 workflow
- 当前 job state
- `task_ref/task_id/task_hash`
- `payload_json`
- `version`
- `lease_owner/lease_until`

它回答的是：

**当前到底是哪条任务、谁拿到了执行权、payload 是否还能重建。**

### 两者合起来

`confirm` 才能同时知道：

- 审批有没有 stale / expired
- job 有没有被别人先执行 / 先取消

## 4. `job_event` 是恢复和关联的核心账本

`job_event` 不是附属日志，而是多个链路的真实依据。

### 典型用途

- `downloader.approval_pending` / `downloader.approval_confirmed`
- `downloader.completed_observed`
- `import.succeeded`
- `metadata.*`
- `subtitle.*`
- `refresh.*`
- `cleanup.*`
- `adult_archive.*`
- `telegram.summary_sent`

### 典型消费者

- cleanup 用最近一次 `import.succeeded` 反查 source/target 关联
- Telegram completion summary 用事件流推断后处理是否 finished
- adult archive 会把归档和保留期清理写回事件流

## 5. `download_monitor` 不是 UI 缓存

它记录：

- 当前 downloader status code
- 当前 percent_done
- 是否已完成
- 首次完成观察时间
- 最近观察时间
- Telegram progress card 绑定信息

所以它既服务：

- `status`
- 自动导入触发
- 下载完成轮询
- Telegram live progress

也服务：

- PT 最小做种窗口判断

## 6. `bt_pending_state` 是 BT 支线的轻状态机

当前持久化 stage 包括：

- processing path
- classification
- TMDB association
- raw BT destination
- duplicate override

这类状态有两个来源：

- `bot_data` 里的内存映射
- `bt_pending_state` 表里的持久化兜底

因此 BT follow-up 在重启后仍有机会恢复，而不是完全丢失上下文。

## 7. in-memory 与 durable state 的分工

### 进程内缓存

- `_recent_candidates_by_chat`
- pending add runtime state
- pending import copy-fallback identities
- channel contact 映射

### 持久化兜底

- `candidate_mapping`
- `bt_pending_state`
- `jobs`
- `approval_record`
- `download_monitor`
- `job_event`

这说明项目的真实策略不是“完全无状态”，也不是“所有细节都立刻落库”，而是：

**交互体验走轻缓存，副作用边界和恢复边界走持久化真相。**

## 8. 一条普通观影任务的状态演进

```text
搜索 -> candidate_mapping
选资源 -> approval_record(pending) + jobs(pending_approval)
confirm/auto-confirm -> approval_record(approved) + jobs(completed) + download_monitor(register)
status 完成观察 -> download_monitor(is_complete=1) + job_event(downloader.completed_observed)
auto import -> approval_record(import pending/approved) + jobs(import pending/completed)
导入成功 -> job_event(import.succeeded)
后处理 -> job_event(metadata/subtitle/refresh)
cleanup -> 读取 import.succeeded 关联，再写 cleanup 事件
```

## 9. 一条 adult BT 任务的状态演进

```text
adult_bt source -> adult duplicate check
通过后创建下载 pending -> adult_content_registry(current_status=pending/downloading)
下载完成 -> download_monitor 完成观察
auto follow-up -> AdultArchiveService
归档成功 -> job_event(adult_archive.succeeded) + adult_content_registry(archived_present)
保留期到 -> job_event(adult_archive.retention_cleanup_succeeded) + adult_content_registry(archived_deleted)
```

## 10. 设计层面的真实结论

- `candidate_mapping` / `clarification_state` 服务“这轮对话怎么继续”
- `approval_record` / `jobs` 服务“这次副作用还能不能执行”
- `job_event` / `download_monitor` 服务“执行过什么、现在进行到哪”
- `adult_content_registry` / `bt_subscription_item` / `watchlist_item` 服务“跨轮次长期状态”

理解这层以后，很多行为就不再神秘：

- 为什么 stale confirm 会被拒绝
- 为什么 cleanup 必须依赖 import 事件
- 为什么重启后 Telegram progress 还能继续刷新
- 为什么 adult BT 能继续走归档和保留期清理
