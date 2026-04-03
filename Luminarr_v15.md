# Luminarr v15：正式执行版主文档（结合 review 修订版）

> 这是一份面向真实部署、真实维护、真实迭代的唯一执行总纲。  
> 它既是产品边界说明书，也是运行时契约文本，也是 AI / 人类协作开发的制度源。

---

## 0. 一句话总纲

**Luminarr v15 = 一个面向 2–4 人自托管影视自动化场景的轻量自然语言 Harness。**

当前固定画像：
- Telegram 私聊唯一入口
- TMDB 唯一元数据源
- Prowlarr 唯一搜索聚合器
- Transmission 唯一下载器
- Emby 唯一媒体服务器
- SQLite 唯一数据库
- Docker Compose 唯一部署方式
- 单实例 / 单进程 / 单机
- 电影优先

系统目标不是“更像一个通用 agent”，而是：

1. **副作用动作有明确边界**
2. **执行所有权有明确真相来源**
3. **失败后可以按阶段恢复**
4. **模型异常对用户尽量透明**
5. **不该用 AI 的地方就不要用 AI**

---

## 1. 当前边界

### 当前只做这条主链
意图理解  
→ TMDB 解析  
→ Prowlarr 搜索  
→ 用户选择  
→ 审批  
→ 提交 Transmission  
→ 查询下载状态  
→ 入库  
→ 刷新 Emby

### 当前明确不做
- Sonarr / Radarr
- PostgreSQL / Redis / MQ
- Webhook 部署
- Telegram 群聊
- Web / 桌面端
- 通用插件系统
- 通用 MCP runtime
- 自动删种 / 自动删源文件
- 解压压缩包
- 复杂自动重命名模板
- 自动 watchlist 下载
- 通用多 Agent 协作平台

---

## 2. 六层架构

### 2.1 Channel Layer
当前只保留 Telegram 私聊 Bot。

职责：
- 接收消息
- 发送海报卡片、候选列表、审批文本、状态文本
- 处理 callback / command / text routing

### 2.2 Parser / Planner Layer
职责：
- 识别意图
- 提取参数
- 决定是否需要澄清
- 选择工具或工作流动作

核心原则：
- parser-first，LLM-fallback
- 规则能解决的不用模型
- 恢复、审批校验、幂等、执行真相不交给模型

### 2.3 Workflow / Job Layer
职责：
- 维护任务状态机
- 驱动阶段执行
- 管理等待态、审批态、失败态、恢复态
- 保证阶段重放而不是整链重跑

### 2.4 Tool Layer
核心工具固定为：
- `search_media`
- `add_to_downloader`
- `get_download_status`
- `import_to_library`
- `refresh_media_server`
- `manage_watchlist`

每个工具必须有文档可查的契约：
- `purpose`
- `input`
- `output`
- `side_effects`
- `idempotency_key`
- `concurrency_safe`
- `requires_approval`
- `retry_scope`
- `failure_codes`

### 2.5 Integration Layer
固定对接：
- TMDB Client
- Prowlarr Client
- Transmission Client
- Emby Client

### 2.6 State / Storage / Observability Layer
职责：
- SQLite 持久化
- 去重
- 事件记录
- 恢复
- 结构化日志
- 健康探针
- 审计

---

## 3. Prompt 组装与控制面契约

Prompt 不是文风问题，而是控制面。

固定分层：

```text
system_base
  + project_rules
  + job_context
  + tool_result_summary
  + user_intent
  + response_style
```

优先级固定为：

```text
system_base > project_rules > job_context > tool_result_summary > user_intent > response_style
```

### 允许模型做的事
- 规则解析不稳定时做意图补全
- 多候选含混时生成澄清文案
- 将结构化结果组织成用户可读回复

### 不允许模型做的事
- 审批再校验
- 幂等判断
- lease 抢占
- 执行结果真相判断
- 后台恢复
- scheduler tick

---

## 4. 搜索与元数据契约

### 固定搜索目标
Luminarr 的搜索不是把用户原话直接扔给资源站，而是：

1. 先用 TMDB 解析媒体对象
2. 用中文标题 / 简介 / 卡片文本展示
3. 用英文标题 + 年份发送给 Prowlarr
4. 若无结果，再回退原始语言标题 + 年份
5. 仅 TMDB 不可用或无命中时，回退到 parser-normalized 原查询

### 固定约束
- 不自动用中文标题直搜 Prowlarr
- 不把分辨率/来源/编码拼进主搜索词
- 质量偏好只参与排序，不参与主搜索词构造

---

## 5. 工具调度与安全并发

这是 v15 吸收 review 后的关键增强之一。

### 5.1 调度哲学
- **只读 / 纯查询工具可安全并发**
- **有副作用工具必须串行**
- **同一 job 的副作用路径不得并发**
- **没有执行所有权就不能继续副作用路径**

### 5.2 当前推荐划分
- 可并发：`search_media`、`get_download_status`
- 串行：`add_to_downloader`、`import_to_library`、`refresh_media_server`
- `manage_watchlist` 当前先按串行处理

### 5.3 注意
这是一条**正式工程纪律**，不等于当前已经实现了完整的并发调度器。  
当前阶段先把它写成契约，后续再逐步落实到 executor / orchestration 层。

---

## 6. LLM 物理异常的响应式恢复

这是 v15 新提升为正式制度的一部分。

### 6.1 要处理的异常
- `413 Payload Too Large`
- `max_output_tokens` 截断
- 上下文过长导致的同类失败

### 6.2 恢复原则
系统收到这类异常时，不应直接把底层崩溃暴露给 Telegram 用户。  
应该优先尝试：

1. 丢弃旧的澄清历史
2. 丢弃过长的 `tool_result_summary`
3. 仅保留：
   - `system_base`
   - `project_rules`
   - 当前 `job_context`
   - 必要 `user_intent`
4. 同轮次透明重试一次

### 6.3 边界
- 不允许无限重试
- 不允许因恢复动作本身导致新的死循环
- 如果透明重试失败，必须回到确定性错误文本，而不是让模型继续乱补

> 说明：当前把这条写成正式制度，代码层面仍属后续实现项。

---

## 7. 模糊意图的探索代理隔离

### 7.1 为什么需要
当用户说：
- “诺兰那部星际穿越”
- “昨天那部不对，换另一个”
- “这个片子不是 2014 那版”

这种模糊查询很容易让多轮试错污染主状态机。

### 7.2 v15 规则
允许在高歧义搜索中使用**只读探索子流程（Explore Agent / Explore Subflow）**。

它可以：
- 反复比对 TMDB 候选
- 组织澄清文本
- 辅助海报对比
- 做只读搜索

它不可以：
- 写主 workflow 状态
- 写审批状态
- 下单下载
- 修改导入状态

### 7.3 写回主状态机的唯一内容
只能是最终确认后的结构化结果，例如：
- `tmdb_id`
- 标准英文标题
- 原始标题
- year
- media_type

---

## 8. 审批与审批唤醒后的上下文重建

### 8.1 审批原则
所有副作用路径必须先经过规则层与上下文层校验。  
审批矩阵的唯一规则源为动作表，不允许在代码别处发明平级规则。

### 8.2 当前必须审批的动作
- `add_to_downloader`
- `import_to_library.copy_fallback`
- `retry_failed_stage`
- 未来删除类动作

### 8.3 当前现实状态
代码中已经落地的是：
- `import <id/hash>` 进入 pending
- `confirm <id/hash>` 执行 import + refresh

### 8.4 v15 新规则：审批唤醒后重建工作内存
当用户点击确认或发送 `confirm` 时：

不要把之前用于选片、澄清、闲聊的长历史重新喂给模型。  
必须只按下面的层次重建一个极小执行上下文：

```text
system_base
+ project_rules
+ current_job_context
+ current_approval_context
+ minimal tool_result_summary (if needed)
```

### 8.5 原因
审批唤醒的本质是执行阶段，不是探索阶段。  
需要的是“此时此刻必须知道的最小事实”，而不是整段历史。

---

## 9. 低成本挫败感熔断

这是 v15 新吸收的另一条关键改进。

### 9.1 原则
优秀的 Harness 必须知道什么时候**停止继续用 AI**才是最好的用户体验。

### 9.2 建议检测词
在 Parser 层增加正则或关键词规则检测：

- 不对
- 停
- 重来
- 换一个
- 算了
- 取消

### 9.3 触发时机
主要在这些阶段触发：
- `awaiting_clarification`
- `awaiting_user_choice`
- `pending_approval`

### 9.4 触发后的行为
优先走确定性短路，而不是继续调用 LLM：

- reset 当前临时选择
- 丢弃已废弃候选
- 回到最简单的下一步提示
- 必要时直接取消当前 job

---

## 10. 状态机、幂等与恢复

### 10.1 最小状态集合
- `received`
- `planning`
- `awaiting_clarification`
- `awaiting_user_choice`
- `pending_approval`
- `approved`
- `dispatching`
- `downloading`
- `import_pending`
- `refresh_pending`
- `completed`
- `failed`
- `cancelled`
- `expired`

### 10.2 必须持久化的关键标识
- `job_id`
- `telegram_update_id`
- `callback_query_id`
- `chat_id`
- `user_id`
- `tmdb_id`
- `candidate_id`
- `info_hash`
- `transmission_torrent_id`
- `approval_id`

### 10.3 执行所有权
即使用 SQLite，也要有明确的最小执行所有权协议：

- `jobs.version`
- `lease_owner`
- `lease_until`

当前代码只在 import-confirm 路径里有 approval-record-local 的最小 lease/version。  
v15 要求后续把这条原则正式推广到更完整的 workflow 真相源。

---

## 11. Observation、日志与事件

### 11.1 最小事件集
- `job.created`
- `job.state_changed`
- `job.recovered`
- `tool.called`
- `tool.succeeded`
- `tool.failed`
- `approval.requested`
- `approval.approved`
- `approval.denied`
- `approval.expired`
- `import.completed`
- `import.failed`
- `refresh.completed`
- `refresh.failed`

### 11.2 写入规则
每个事件至少落两处：
1. `job_events`
2. 结构化日志

---

## 12. 当前路线重排（v15 最重要的路线修正）

watchlist 不再是最近一步。  
v15 的正确顺序是：

1. `telegram_updates` 去重真相源
2. `jobs.version + lease_owner + lease_until`
3. approval-wake context rebuild
4. frustration detector / reset short-circuit
5. `add_to_downloader` 的 pre-dispatch approval
6. 之后再回到 watchlist baseline

原因很简单：  
**先补控制层，再补业务面。**

---

## 13. 仓库文件优先级

当仓库文档互相冲突时，按这个顺序解释：

1. 本执行文档
2. `docs/DECISIONS.md`
3. `docs/NEXT_STEP.md`
4. `docs/STATUS.md`
5. `README.md`
6. `AGENTS.md`

---

## 14. 一句话执行总结

> **Luminarr v15 = 一个Telegram 私聊唯一入口的垂直媒体自动化 Harness；它保留 TMDB-first 搜索、import-confirm、最小 lease/version 防重放等已落地能力，同时正式吸收“只读安全并发、LLM 物理异常响应式恢复、模糊查询探索隔离、审批唤醒上下文重建、挫败感短路”这五条工程纪律，并将下一阶段优先级重新拉回执行卫生与控制层。**
