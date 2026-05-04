<!-- /autoplan restore point: /home/alex/.gstack/projects/milikii-luminarr/main-autoplan-restore-20260503-213611.md -->
<!-- /autoplan seed: rewritten after real smoke findings on 2026-05-03 -->

# Telegram Automation + MoviePilot-Level Post-Processing After Explicit Selection

生成时间：2026-05-03  
状态：draft for `/autoplan` review

## 1. Goal

把 Telegram 的观影 PT 主链改成“**只在真正需要人判断的地方停下来**”，并把导入后的媒体产物质量提升到接近 MoviePilot：

1. 用户只手动决定：
   - 走 `观影 PT 链` 还是 `BT 成人链`
   - 哪个确定的作品
   - 哪个确定的资源
2. 一旦资源已明确，系统应自动完成：
   - 下载投递
   - 下载完成观察
   - 导入
   - metadata 刮削
   - 字幕翻译
   - 媒体库刷新
3. 导入后的媒体产物应尽量达到可直接入库观感：
   - 目录结构清晰稳定
   - 文件名中文化 / 成品化
   - metadata / NFO 不再只有最小字段
   - 海报 / 背景图尽量落盘
   - 演员中文名与演员头像能力补齐
4. 用户应收到低噪音、可读的关键通知，而不是被多层 `confirm` / 中间步骤打断。

本计划优先覆盖 **四渠道共用的观影 PT 自动化主链（Telegram / Feishu / personal WeChat / WeCom）**。  
`BT 成人链` 保持现有成人电影归档语义，不并入 TMDB / 刮削 / 字幕 / refresh。

---

## 2. User Intent

用户当前追求的是“自动化优先”，不是“把 every side effect 都再确认一遍”。

明确方向：

- **删掉 PT 资源选择后的下载确认**
  - 选中资源后，直接下载
- **删掉导入确认**
  - 下载完成后，直接导入并执行后处理
- **direct magnet 尽量少问**
  - 除了 `观影 PT 链 / BT 成人链` 这种真正的语义分叉
  - 以及在媒体身份不明确时的最低限度补充
  - 其余信息尽量从磁链标题、torrent 名称、既有上下文和 TMDB 自动推断

---

## 3. Current Smoke Facts

### 3.1 We confirmed in real Telegram smoke

- `confirm <task_ref>` 后，用户确实会收到即时回包：
  - `已添加下载：...`
  - `任务 ID: ...`
  - `任务 Hash: ...`
- `status <任务ID或Hash>` 当前是 **手动拉取**，不是自动推送。
- 下载完成后的后半段，目前还没在这轮里跑通到终点；因此：
  - 自动完成通知
  - 自动导入通知
  - 刮削 / 字幕 / refresh 的用户可见通知
  还没有完整的新鲜实证。

### 3.2 We uncovered two real implementation issues

1. **状态路由问题**
   - 旧实现里，`confirm` 成功后 completed job 没稳定落真实 downloader identity
   - 导致 `status <真实 task id>` 会 miss 或串到错误任务
   - 当前仓库代码已经修复：
     - completed job truth 用真实 `task_id/task_hash`
     - 历史任务命中后，查询下载器会优先使用持久化真实 identity

2. **Transmission dispatch path 问题**
   - 之前 `.env` 的 `DOWNLOADER_INSTANCES` 只写了宿主机路径 `/data/downloads/tr`
   - 没写容器内 `dispatch_download_dir=/downloads/complete`
   - 导致容器内 Transmission 收到一个错误的内部下载路径，任务停在 `No data found`
   - 当前本机 `.env` 已修复成：
     - `tr-pt|...|/data/downloads/tr|/downloads/complete`
     - `tr-bt|...|/data/downloads/tr-bt|/downloads/complete`

### 3.3 Real completed PT candidate ready for post-download validation

以下已完成 PT 任务适合作为后半段验证样本：

- `task_hash = b49089c888d789d96a989acd709e7437a234c102`
- `task_id = 20`
- `title = Akron.2015.1080p.AMZN.WEB-DL.DDP2.0.H.264-NZMA.mkv`
- `TMDB identity already present`
  - `title = 爱的进行时`
  - `original_title = Akron`
  - `tmdb_id = 361018`
  - `year = 2015`

这条任务单文件、已完成、带英文字幕缺口，适合验证：

- 自动导入
- metadata scraping
- 字幕翻译
- media server refresh
- 对应通知与 job_event 真相

### 3.4 Real post-download smoke findings on the completed PT sample

针对 `b49089c888d789d96a989acd709e7437a234c102 / task_id=20`，本轮已拿到真实后半段证据：

- **下载完成观察**
  - `job_event` 存在 `downloader.completed_observed`
- **导入**
  - `job_event` 存在：
    - `import.approval_pending`
    - `import.approval_confirmed`
    - `import.succeeded`
  - 目标路径：
    - `/data/library/movies/Akron DDP2 H NZMA E264.mkv`
- **硬链接**
  - 源文件与目标文件 inode 相同，确认是硬链接而不是复制
- **metadata scraping**
  - `job_event` 存在 `metadata.succeeded`
  - 产物存在：
    - `Akron DDP2 H NZMA E264.metadata.json`
    - `Akron DDP2 H NZMA E264.nfo`
- **字幕翻译**
  - `job_event` 存在 `subtitle.failed`
  - 真实失败原因：
    - `系统缺少 ffprobe/ffmpeg，无法检查内嵌字幕`
- **refresh**
  - `job_event` 存在 `refresh.succeeded`
  - 文案为：`媒体库刷新成功。`

这轮 smoke 也明确暴露了当前“质量不足”而非“能力缺失”的问题：

- **命名质量不足**
  - 导入目标文件名被规范化成：
    - `Akron DDP2 H NZMA E264.mkv`
  - 对 Emby / 媒体库来说，这个名字不够像稳定、可读、可被优雅识别的成品命名
- **metadata 内容过薄**
  - 当前 metadata JSON 只包含最小 TMDB identity 和 subtitle trusted name map
  - NFO 只写了：
    - 标题
    - 原始标题
    - 年份
    - `tmdbid`
- **海报 / 背景图缺失**
  - 本轮样本里 `fanart.poster_url` 和 `fanart.backdrop_url` 都为空
  - 因此没有任何 poster / backdrop 文件落到媒体库

这说明下一阶段的重点不应只是“让导入链自动跑”，还必须把：

- 命名质量
- metadata 丰富度
- 海报 / 背景图
- 字幕翻译运行前提

一起提升到接近 MoviePilot 级别，而不是满足于“有个名字就算刮削成功”。

---

## 4. Locked Product Direction

### 4.1 Keep these manual decisions

- `观影 PT 链` / `BT 成人链`
- 作品选择
- 资源选择

### 4.2 Remove these user-facing confirmations

- PT 资源选定后的 **下载确认**
- 下载完成后的 **导入确认**

### 4.3 Keep these internal safety guarantees

用户不再看到 `confirm`，不代表内部真相要粗暴删除。

推荐保留并复用现有：

- `approval_record`
- `jobs`
- `lease_version / executed_version`
- stale / duplicate / recovery contracts

方式改为：

- **内部自动确认**
  - 用户选择资源后，系统在同一动作内自动走 pending -> confirm -> dispatch
  - 用户只看到最终的“已添加下载”
- **内部自动导入**
  - 下载完成观察后，系统在同一后续动作内自动走 import pending -> confirm -> execute
  - 用户只看到“自动导入开始 / 导入成功 / 后处理总结”

换句话说：  
**删除的是用户摩擦，不是内部真相。**

---

## 5. Proposed UX

### 5.1 Search / PT resource path

当前：

`搜索 -> 选作品 -> 选资源 -> 待确认下载 -> confirm -> 已添加下载`

目标：

`搜索 -> 选作品 -> 选资源 -> 已添加下载`

用户不再收到：

- `待确认：下载`
- `请发送 confirm ...`

用户会直接收到：

- `已添加下载：...`
- `任务 ID: ...`
- `任务 Hash: ...`

### 5.2 Download completion path

当前：

`status / scheduler -> completion observed -> 导入待确认 -> confirm import -> 导入`

目标：

`status / scheduler -> completion observed -> 自动导入 -> 后处理`

用户不再收到：

- `导入待确认：...`
- `请发送 confirm ... 执行导入`

### 5.3 Direct magnet / direct torrent path

当前 direct magnet 观影链过于串行：

1. 先问 `观影 PT 链 / BT 成人链`
2. 若选观影链，再问 `movie / series / anime`
3. 再让用户手打标题做 TMDB 关联

目标：

1. 保留 `观影 PT 链 / BT 成人链` 这一步
2. 如果用户选 `观影 PT 链`：
   - 先从 magnet `dn=`、torrent title、已有聊天上下文中提取候选标题 / 年份
   - 自动尝试 TMDB 关联
   - 只有当：
     - 关联失败
     - 多结果不确定
     - 媒体类型高歧义
     时，才追问 `movie / series / anime` 或标题补充

用户理想体验：

- “给你磁力链接”
- “我选观影 PT 链”
- 系统尽量自己推出标题 / 年份 / TMDB
- 真不确定时再问最少的问题

---

## 6. Notification Model

目标不是多发消息，而是**只发关键节点**。

### 6.1 Keep

- 资源选定后：
  - `已添加下载：...`
  - `任务 ID / Hash`
- 手动 `status`
  - 仍然保留

### 6.2 Add

- 下载完成观察到时：
  - `下载完成，开始自动导入：...`
- 导入与后处理收尾时：
  - 一条聚合总结消息，包含：
    - 导入成功 / 失败
    - metadata scraping 成功 / 失败
    - 字幕翻译 成功 / 跳过 / 失败
    - media server refresh 成功 / 失败

### 6.3 Do not add by default

- 周期性自动进度推送

理由：

- 这类通知噪音高
- 现有 `status` 手动拉取已经够用
- 当前用户主要抱怨的是确认摩擦，不是进度消息不够多

---

## 7. Technical Shape

### 7.1 PT resource selection should auto-confirm downloader dispatch

候选资源点击 / 选择后：

- 仍走现有 `PendingAddContext`
- 仍写 pending approval / pending job
- 但同一动作内自动调用现有 confirm execution tail
- 成功后：
  - 用户只看到最终 dispatch 成功消息
  - 不再看到 pending approval 文本

涉及模块：

- `app/services/add_to_downloader.py`
- `app/bot/private_chat_selection_runtime.py`
- `app/services/telegram_pt_resource_cards.py`
- `app/bot/telegram_runtime_adapter.py`

### 7.2 Completion observer should auto-confirm import execution

下载完成观察后：

- `PostDownloadAutoImportService` 不再只创建导入待确认
- 改为：
  - 准备导入
  - 自动 confirm import
  - 直接执行导入 / 硬链接或 copy fallback 分支

但：

- 仍保留内部 approval/job/lease 真相写入
- copy fallback 这种真正高风险分支是否还要保留人工确认，需要单独明确

推荐：

- **同盘硬链接路径**：自动执行
- **跨文件系统 copy fallback**：仍保留显式人工确认

原因：

- 复制会额外占大块磁盘
- 这是和普通自动导入性质不同的重副作用

涉及模块：

- `app/services/post_download_auto_import.py`
- `app/services/import_to_library.py`
- `app/services/import_transfer_execution.py`

### 7.3 Direct magnet should attempt zero-question TMDB association

新增一个“自动名称解析优先”层：

- 输入：magnet / torrent title / candidate title
- 输出：
  - candidate media title
  - candidate year
  - media type confidence
  - TMDB query suggestion

只有在低置信度时才 fallback 到显式问询。

涉及模块：

- `app/bot/bt_processing_path_runtime.py`
- `app/bot/bt_tmdb_association_runtime.py`
- `app/services/search_media.py`
- 可能新增一个专门的 BT title normalization helper

### 7.4 Import naming and library shape should prefer confirmed media identity

目标不是“把 release name 稍微洗一下”，而是让媒体库更像成品：

- 电影：
  - 优先命名为 `中文名 (年份)`，其次 `原名 (年份)`
  - 目标形态优先收口为目录 + 主文件，而不是平铺一个 release 风格文件名
- 剧集：
  - 目录名优先使用已确认作品名
  - 集文件名保留可读的 `SxxExx` 结构

涉及模块：

- `app/services/import_prepare_state.py`
- `app/services/import_transfer_execution.py`
- `app/services/import_to_library.py`

### 7.5 Metadata / NFO should become Emby-friendly, not minimum viable

当前真实样本只写了 title/originaltitle/year/tmdbid，这对 Emby 远远不够。

目标补齐：

- 剧情简介 / overview
- rating / vote_average / vote_count
- genres
- countries / studios（如 TMDB 可得）
- cast 列表
  - 演员中文名
  - 角色名
  - 演员头像 URL / 落盘策略

涉及模块：

- `app/services/metadata_scraper.py`
- `app/clients/tmdb.py`

### 7.6 Poster / backdrop / actor image should be artifact-grade

当前代码里已有 poster/backdrop 下载能力，但真实样本没有稳定落地。

目标：

- movie / directory target 都能稳定落 poster / backdrop
- fanart 缺图时继续走 TMDB fallback
- 演员头像至少先进入 metadata/NFO truth，必要时再落盘

涉及模块：

- `app/services/metadata_scraper.py`
- `app/clients/fanart.py`
- `app/clients/tmdb.py`

---

## 8. Scope

### In scope

- Telegram 观影 PT 主链
- PT 资源选择后直接下载
- 下载完成后自动导入
- metadata / subtitle / refresh 自动后处理
- direct magnet 观影链最小问询化
- 用户可见关键通知收口
- 电影 / 剧集导入后的目录结构与命名质量提升
- metadata / NFO 丰富化
- 海报 / 背景图真实落盘能力强化
- 演员中文名 / 角色名 / 演员头像支持
- 使用已完成 PT hash `b49089c888d789d96a989acd709e7437a234c102` 验证导入后半段

### Out of scope

- 删除底层 `approval_record / jobs / lease` 真相模型
- 改 `BT 成人链` 的归档语义
- 给所有下载都做自动进度推送
- 改 raw_bt 目录选择主线
- 一步到位复制 MoviePilot 的全部媒体管理能力（如多媒体服务器特化适配、刮削源插件生态）

---

## 9. Acceptance Criteria

- 用户在 Telegram 里选定 PT 资源后，不再看到“待确认下载 / confirm”提示，而是直接收到下载投递结果
- 下载完成后，媒体型 PT 任务自动进入导入链，不再要求用户再 `confirm import`
- 完成导入后，用户至少能收到 1 条聚合总结，覆盖导入 / metadata / subtitle / refresh 结果
- direct magnet 观影链在高置信度标题下，不再强制每次都问 `movie / series / anime + 手打标题`
- 默认部署语义下，不把 copy fallback 当作主设计约束
- 已完成 PT 样本 `b49089c888d789d96a989acd709e7437a234c102` 的导入后半段验证有新鲜证据
- 真实样本导入后，媒体库产物至少达到：
  - 目录 / 文件命名不再是原始 release 风格
  - metadata / NFO 不再只有最小 identity 字段
  - poster / backdrop 在可得时落盘
  - 演员中文名 / 角色名进入 metadata truth

---

## 10. Risks

- 如果直接删除内部 approval/lease 真相，而不是只删用户确认，会打碎 stale reject、恢复和重放保护
- 若未来实际出现跨文件系统路径，仍需重新确认 fallback 策略
- direct magnet 自动识别做得太激进，会把低置信度标题错误关联到 TMDB
- 通知设计若拆成过多消息，会从“自动化”退化为“通知轰炸”

---

## 11. Recommended Implementation Order

1. 观影 PT 资源选择后的自动 dispatch
2. 下载完成后的自动 import（硬链接路径）
3. 导入后聚合总结通知
4. direct magnet 自动标题解析 + 降问询
5. 导入目录结构 / 命名成品化
6. metadata / NFO 丰富化
7. poster / backdrop / actor image 能力补齐
8. 四渠道适配统一自动化主链

---

## AUTOPLAN REVIEW

### Phase 1 — CEO Review

#### 0A. Premise Challenge

- **Premise accepted:** 用户真正想自动化的是“已经完成判断之后的动作”，不是把所有歧义都静默跳过。
- **Premise accepted:** `观影 PT 链 / BT 成人链` 仍然是合理的显式分叉，因为这决定后半段是否进入 TMDB / 导入 / 刮削 / 字幕 / refresh。
- **Premise challenged:** “把确认环节删掉”不能等于“删除内部 approval / jobs / lease 真相”。
  原因：当前恢复、幂等、stale reject、重放保护都压在这套真相上。删除用户摩擦是对的，删除内部真相是错的。
- **Premise accepted with guardrail:** direct magnet 应该尽量少问，但不能在低置信度标题上假装识别成功。
- **Premise accepted:** 四渠道不应长期维持“Telegram 自动化、其他渠道手动确认”的分裂体验；shared private-chat runtime 现有结构支持统一收口。

#### 0B. What Already Exists

| Sub-problem | Existing code / contract |
| --- | --- |
| PT 资源选定后的下载投递 | `AddToDownloaderService` + `PendingAddContext` + `confirm_add_by_task_ref()` |
| 下载完成观察 | `download_monitor` + `GetDownloadStatusService` + `PostDownloadAutoImportService` |
| 导入与后处理 | `ImportToLibraryService` + `ImportPostProcessingService` |
| metadata / subtitle / refresh | 已存在于 `import_post_processing`，但当前对用户只回 refresh 文本 |
| direct magnet 处理链 | `bt_processing_path_runtime` + `bt_tmdb_association_runtime` |

#### 0C. Dream State Mapping

```text
CURRENT
  搜索 -> 选作品 -> 选资源 -> 待确认下载 -> confirm
  下载完成 -> 导入待确认 -> confirm import
  direct magnet -> 选链路 -> 选类型 -> 手打标题 -> TMDB

THIS PLAN
  搜索 -> 选作品 -> 选资源 -> 自动下载
  下载完成 -> 自动导入 -> 自动后处理 -> 聚合总结通知
  direct magnet -> 选链路 -> 自动识别标题/年份 -> 仅低置信度时补问

12-MONTH IDEAL
  Telegram 主链只在真正有歧义时打断用户
  观影 PT / BT 成人 / raw_bt 三类后半段语义清楚
  内部恢复与幂等真相保留，但用户几乎感知不到
```

#### 0C-bis. Implementation Alternatives

| Approach | Summary | Pros | Cons | Verdict |
| --- | --- | --- | --- | --- |
| A | 删用户确认，保留内部真相并自动 confirm，四渠道一起收口 | 最符合自动化目标；风险最可控；能复用现有 shared runtime 和恢复边界 | 实现要绕现有 pending/confirm path 一层，通知模板也要四渠道统一 | **Recommended** |
| B | 彻底删除 approval/jobs/lease | 用户面最“干净” | 直接打碎 stale / recovery / 幂等保护；高回归风险 | Reject |
| C | 保留当前确认，只美化文案 | 改动最小 | 不能解决用户核心抱怨 | Reject |

#### 0D. Scope Decisions

- **Accepted now**
  - PT 资源选择后的自动下载
  - 下载完成后的自动导入（按当前默认硬链接语义）
  - 导入后聚合总结通知
  - direct magnet 自动标题解析 + 降问询
  - 四渠道共用同一套自动化主链
- **Deferred**
  - 自动周期性进度推送
  - `BT 成人链` 语义重做

#### 0E. Temporal Interrogation

- **Hour 1 value**
  - 用户选 PT 资源后不再看到“待确认下载”
- **Hour 6 value**
  - 下载完成能自动入库，不再手发 `import` / `confirm import`
- **6-month regret if wrong**
  - 如果为了省一步确认而删掉内部 approval/lease，后面会在重复执行、恢复失败、误导入上付出更大代价

#### 0F. CEO Mode Selection

- Mode: `SELECTIVE_EXPANSION`
- Reason:
  - 扩的是真正和用户抱怨直接相关的自动化链路
  - 不顺手把全渠道、全通知、全 BT 支线一起卷进来

#### CEO Error & Rescue Registry

| Failure | User sees | Rescue |
| --- | --- | --- |
| 自动下载 dispatch 失败 | 资源点了但没加进去 | 回退 pending approval truth；给出单条失败通知 |
| 自动导入失败 | 下载完成但未入库 | 保留下载完成真相；发“自动导入失败，可手动 import” |
| direct magnet 自动识别错标题 | 错 TMDB / 错入库 | 低置信度时必须 fallback 到人工补充 |
| direct magnet 自动识别错标题 | 错媒体入库 / 错 TMDB | 低置信度时必须 fallback 到人工确认 |

#### CEO Failure Modes

- 资源选定自动下载后，如果不保留内部 approval/job truth，重复点击与重启恢复会立即退化。
- direct magnet 自动识别如果没有置信度闸门，会把“减少问询”做成“错误自动化”。
- 四渠道如果各自实现一套自动化，会让 shared runtime 重新分叉，维护成本迅速失控。

#### CEO Completion Summary

| Dimension | Verdict |
| --- | --- |
| Right problem | Yes |
| Scope calibration | Good, with copy-fallback guardrail |
| Existing leverage | Strong |
| Main product risk | Over-deleting internal truth |
| Main user value | Remove friction after explicit selection |

### Phase 2 — Design Review

- UI scope: **Yes**
- Initial rating: **7/10**

#### Findings

- 信息架构方向是对的：用户只在“链路 / 作品 / 资源”三个有信息增益的点停下。
- 当前计划还缺一条明确的“后处理总结消息模板”，否则实现时容易重新散成多条低质量提示。
- `status` 应继续保留为手动拉取，不建议默认上自动周期推送，否则会把低噪音目标打碎。

#### Design Scores

| Pass | Score | Note |
| --- | --- | --- |
| Information Architecture | 8/10 | 主线更短更清楚 |
| Interaction State Coverage | 6/10 | 还需明确 dispatch fail / auto-import fail / copy-fallback 分支文案 |
| User Journey | 8/10 | 摩擦显著减少 |
| AI Slop Risk | 7/10 | 若通知模板不收口，容易退回工程提示 |
| Design System Alignment | 7/10 | 仍沿 Telegram-first 主线，不破坏已有卡片方向 |
| Responsive & Accessibility | 7/10 | 聊天 UI，风险较低 |
| Unresolved Design Decisions | 0 | 当前用户已明确接受“默认按硬链接自动化语义设计” |

#### Design Recommendation

- 自动化后的通知应收口为 3 个层级：
  - `已添加下载`
  - `下载完成，开始自动导入`
  - `导入 / metadata / subtitle / refresh 聚合总结`

### Phase 3 — Eng Review

#### Architecture Review

- **Good:** 计划已经明确“删用户确认，不删内部真相”，这是唯一可行的工程方向。
- **Good:** 现有代码 leverage 很高，`add_to_downloader`、`post_download_auto_import`、`import_to_library` 和 shared private-chat runtime 都能复用。
- **Risk:** 自动下载与自动导入都不能简单跳过现有 confirm tail；应通过“内部自动 confirm”进入现有执行尾链。

#### Code Quality Review

- 需要避免出现两套平行入口：
  - `manual confirm path`
  - `auto confirm path`
- 推荐把自动化实现成对现有 confirm 执行尾部的封装，而不是复制一份新流程。

#### Test Review

必须新增或覆盖：

- PT 资源点击后直接 dispatch，不再返回 pending approval 文本
- 自动下载仍写 approval/job truth，重复点击仍幂等
- 下载完成后自动 import 成功路径
- copy fallback 自动导入策略
- direct magnet 高置信度自动识别
- direct magnet 低置信度 fallback 问询
- 导入后聚合总结通知
- 四渠道 reply formatter / reply_func 统一回归

#### Performance Review

- 自动化本身不是性能热点
- 真正风险在通知风暴与重复后处理
- 需要确保 terminal activity / event guard 继续阻止重复 auto-import

#### Eng Test Plan

```text
Affected flows
1. PT resource selected -> auto dispatch
2. downloader completed observed -> auto import
3. import post-processing -> aggregate notification
4. direct magnet title inference -> low-question path

Critical paths
- duplicate click idempotency
- restart recovery after auto-dispatch
- 四渠道统一自动化不回退为 Telegram-only 特例
- stale confirm compatibility for old records

Edge cases
- TMDB mismatch / ambiguity
- completed download but missing source path
- subtitle translation failure with import success
- refresh failure with import success
```

#### Eng Failure Modes

| Failure mode | Severity | Note |
| --- | --- | --- |
| 删除 approval/lease 内部真相 | Critical | 会破坏恢复和幂等 |
| direct magnet 误识别标题 | High | 错 TMDB / 错入库 |
| 四渠道实现分裂 | High | shared runtime 再次碎裂 |
| 自动导入后通知拆成多条噪音 | Medium | UX 退化 |

#### Eng Completion Summary

| Dimension | Verdict |
| --- | --- |
| Architecture | Sound if internal truth preserved |
| Tests | More needed before implementation |
| Performance | Acceptable |
| Main risk | copy-fallback policy |

### Phase 3.5 — DX Review

- Skip reason: no developer-facing scope detected

---

## Cross-Phase Themes

- **Theme 1: Delete friction, keep truth**
  - CEO / Eng 都确认：用户确认可以删，但 approval/jobs/lease 不能删
- **Theme 2: direct magnet should ask less, not guess recklessly**
  - CEO / Eng 都要求引入自动识别 + 低置信度 fallback，而不是无脑自动化
- **Theme 3: automation should be shared, not Telegram-only**
  - Design / Eng 都支持沿 shared private-chat runtime 一次收口四渠道

---

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|----------------|-----------|-----------|----------|
| 1 | CEO | 删用户确认但保留内部 truth | Mechanical | Explicit over clever | 自动化目标与恢复边界可同时满足 | 彻底删除 approval/lease |
| 2 | CEO | direct magnet 保留链路分叉 | Mechanical | Pragmatic | 观影链 / 成人链后半段完全不同 | 全自动猜链路 |
| 3 | Design | 不加周期性自动进度推送 | Mechanical | Completeness | status 手动拉取已够，避免通知噪音 | 默认进度轰炸 |
| 4 | Eng | auto-import 复用现有 confirm tail | Mechanical | DRY | 避免长出第二套执行分支 | 复制一套新导入流程 |
| 5 | CEO/Eng | 四渠道共用同一套自动化主链 | Mechanical | DRY | 现有 shared private-chat runtime 已具备统一收口基础 | Telegram-only 特例 |

---

## AUTOPLAN REVIEW ADDENDUM — 2026-05-04

### Scope Update

用户已经把目标从“主链自动化”进一步锁到了两条并行主线：

1. 自动化主链
   - 只保留真正需要人工判断的节点
   - 其余下载 / 导入 / 后处理自动执行
2. MoviePilot 级后处理质量
   - 目录结构
   - 中文命名
   - metadata / NFO 丰富度
   - 海报 / 背景图
   - 演员中文名 / 角色名 / 演员头像

### CEO Verdict

- 这不是 scope creep，而是对真实用户价值的必要补全。
- 当前用户真正不满意的，已经从“流程会不会自动跑”转向“媒体库产物像不像成品”。
- 因此计划不应停在自动化链路，还必须把导入后的成品质量拉起来。

### Design Verdict

- Design scope limited but real:
  - Telegram 通知层已基本收口
  - 新的“设计质量”主要体现在媒体库最终观感，而不是 bot UI
- 成败标准是：
  - Emby / Jellyfin 里看到的是成品目录和成品命名
  - 不是 release 风格文件平铺

### Eng Verdict

- 当前真实链路已经证明：
  - 自动下载 / 自动导入 / 硬链接 / 基础 metadata / 字幕翻译 / refresh 都能跑通
- 当前真实链路也已经证明：
  - 离 MoviePilot 水平的主要差距不在“有没有链路”，而在“产物质量不够厚”

建议实施顺序：

1. 目录结构与命名成品化
2. metadata / NFO 丰富化
3. poster / backdrop 真实样本稳定落盘
4. cast truth 扩展为演员中文名 + 角色名
5. `TmdbCreditPerson` 扩展 `profile_path`，再决定 actor avatar 是先写 truth 还是直接落盘
6. 用真实样本回归 Emby 观感，而不是只看单元测试

### No User Challenge

本轮没有新的 user challenge。

原因：

- “做成 MoviePilot 同水平”是当前用户明确表达的方向
- 自动化主链已经有实证基础，不需要再争论是否继续做

### Main Risk

- actor avatar 不是纯本地文件问题，而是“TMDB credits truth -> metadata/NFO -> 媒体服务器实际消费”的跨层问题
- 因此实现时应先补全 truth，再用真实媒体服务器验证显示效果，避免一开始就过度实现本地头像落盘

---

## AUTOPLAN REVIEW ADDENDUM — 2026-05-05

### Scope Recut

用户已经明确把字幕验证后置，当前最有价值的推进顺序变成：

1. 去掉“已经完成明确选择之后”的多余确认
2. 看清各渠道后台通知到底长什么样、哪些渠道真的能发

并且用户已经进一步确认：

- **先从 Telegram 开始**
- **每个渠道单独适配、优化、测试**
- `Feishu / personal WeChat / WeCom` 不再和 Telegram 自动化主链绑成同一轮并行交付
- **“只做硬链接、不做 copy fallback”是全局存储语义决策，但不并入 Telegram 第一刀**

因此，本计划当前不应继续把以下内容绑在同一轮：

- direct magnet 降问询
- MoviePilot 级 metadata / poster / backdrop / cast 质量提升
- 字幕翻译完成态验证
- 硬链接/清理语义的全局重构

这些都是真需求，但不属于这一刀最小、最可验证的 blast radius。

### CEO Verdict

- **方向不变，但范围必须缩小。**
  “显式选择后自动化”仍然是对的；真正要砍的是用户摩擦，不是内部真相。
- **Telegram-first 是正确 wedge。**
  先把一个真实入口做成，再逐个渠道适配，明显优于四渠道同时推进。
- **当前 slice 的用户价值很纯：**
  - 资源选完就下载
  - 下载完成就自动导入
  - 关键节点有低噪音通知
- **现在不要再混 direct magnet。**
  direct magnet 的自动识别和降问询是下一刀，不是这一刀。它会把 TMDB 置信度、媒体类型歧义、标题清洗一起卷进来，明显扩大 blast radius。

### Eng Verdict

- **自动下载 / 自动导入只应该建立在现有 truth 之上。**
  - `approval_record`
  - `jobs`
  - `lease_version / executed_version`
  这些继续保留。
- **“只做硬链接、不做 copy fallback”已经是新产品方向，但不并入这一刀。**
  这条会同时碰 `import_to_library`、`import_transfer_execution`、cleanup、adult archive 和跨文件系统失败语义，blast radius 明显大于 Telegram 自动化主链本身。
- **当前“四渠道通知主线”并不对称。**
  从现有实现看：
  - `Telegram`：支持主动发文本
  - `Feishu`：支持 proactive send
  - `personal WeChat`：支持 proactive send，但依赖登录态
  - `WeCom`：当前 shared sender 明确 `unsupported for channel: wecom`

这意味着本轮“各渠道通知实测”不能写成“四渠道都必须通过”的伪目标，必须写成能力矩阵：

| Channel | Current proactive notification capability | This slice |
| --- | --- | --- |
| Telegram | Yes | In scope smoke |
| Feishu | Yes | In scope smoke |
| personal WeChat | Yes, login-state dependent | In scope smoke |
| WeCom | No proactive send yet | Explicitly deferred / expected fail |

### Revised Implementation Order

1. **Telegram: PT 资源显式选择后的 auto-dispatch**
   - 用户不再看到下载 `confirm`
   - 仍走内部 pending -> confirm -> dispatch tail
2. **Telegram: 下载完成后的 hardlink-path auto-import**
   - 用户不再看到导入 `confirm`
   - 当前仍沿现有默认硬链接路径设计
3. **Telegram: 导入后聚合总结通知**
   - `下载完成，开始自动导入`
   - `导入 / metadata / subtitle / refresh` 汇总成 1 条
4. **Telegram: 实测与排版/通知优化**
5. **Feishu: 单独适配 / 优化 / 测试**
6. **personal WeChat: 单独适配 / 优化 / 测试**
7. **WeCom: 单独适配 / 优化 / 测试**
8. **硬链接 / 清理语义单独收口**
   - 不做 copy fallback
   - PT 跟随 Emby 文件状态决定原任务/原文件生命周期
   - 成人 BT 硬链接 7 天后删除原文件和下载任务，仅保留可查询记录

### Revised Acceptance Criteria

- PT 资源选定后，用户不再看到下载待确认文本
- Telegram 下载完成后的默认硬链接路径，不再要求用户手发导入确认
- 后台自动导入完成后，用户收到 1 条聚合总结，而不是多条工程化碎消息
- Telegram 先完成 1 轮真实通知 smoke，明确看到回包样式
- 其他渠道的通知样式和能力缺口按各自独立任务单独验证

### User Challenge

无。

原因：

- 用户已经明确把当前主线改成“先去确认摩擦，再看通知实测”
- 这个 recut 只是把计划收窄到更容易验证的 wedge，不是在反对目标本身

### New Main Risk

- 如果继续把 `WeCom` 当成“本轮和 Telegram 一样可发”的目标写进计划，执行阶段会被一个当前根本不存在的主动发送能力卡死。
- 如果把 `direct magnet` 一起做，本轮会从“删确认 + 看通知”膨胀成“标题识别 / TMDB / 类型推断 / 后台通知”混合包，验证和回滚都会变差。
- 如果把“禁用 copy fallback + PT/成人 BT 清理语义重构”一起塞进 Telegram 第一刀，本轮会从渠道体验 slice 膨胀成存储/生命周期语义重构，失去最小可验证性。
