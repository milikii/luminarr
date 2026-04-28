# 成人 BT 最小可用闭环计划

生成时间：2026-04-28  
分支：`main`  
状态：DRAFT  
模式：Builder / Open Source

## 1. 这次要解决什么

当前项目里，成人 BT 线已经有一部分真实能力：

- direct magnet 可以分流到 `BT 成人链`
- 成人内容有独立真相表 `adult_content_registry`
- 下载确认链能记录成人内容 ID、分类、历史状态
- 下载完成后会走 `AdultArchiveService`
- 到期后可以清理下载器任务和源资源

但它还没有成为一条“明显可用、明显有成果”的产品线。现在最大的问题不是完全没代码，而是：

- 用户侧看到的结果仍偏系统日志，不像一个顺手的成人 BT 产品面
- 只读搜索、番号识别、历史提醒、来源排序还没有收成稳定的一套使用体验
- 代码里有后半段归档 / 清理，但前半段“搜到什么、该下哪个、为什么”还不够顺
- 最近主线长期停留在 `services` 层结构收口，用户可见成果太少

这轮的目标不是再做平台工程，而是用 **3-6 天** 做出一个可以演示、可以验证、可以明确说“终于有成果”的成人 BT 最小闭环。

## 2. 为什么这条线排第一

相比文档 gate、宿主解耦、配置解耦、继续 services 降本，成人 BT 最小闭环有三个优势：

1. **用户可见**：结果能直接体现在“搜、选、下、归档、清理”上。
2. **已有地基**：当前代码已经有入口分流、registry、archive、retention cleanup，不是从零开始。
3. **止损 token 消耗**：它有清晰终点，不会像结构降本一样无限延长。

## 3. 当前已经存在的可复用能力

### 入口与分流

- `app/bot/private_chat_runtime.py`
- `app/bot/private_chat_bt_processing_runtime.py`
- `app/bot/query_text_runtime.py`

当前已支持：

- direct `magnet:?` 进入 BT 支线
- `观影 PT 链 / BT 成人链 / 纯 BT 下载链` follow-up

### 成人内容真相与后半段

- `app/db/adult_content_registry_repo.py`
- `app/services/adult_archive_service.py`
- `app/services/post_download_auto_import.py`

当前已支持：

- `pending / downloading / archived_present / archived_deleted`
- 下载完成后归档
- 保留期到点后删除下载器任务和源资源

### 搜索与展示基础

- `app/services/search_media.py`
- `app/services/bt_read_only_display.py`
- `app/services/search_reply_formatter.py`
- `app/clients/web_source.py`
- `app/clients/javlibrary_helper.py`

当前已支持：

- 成人站点来源接入
- BT 只读搜索
- 最小 exact-id helper
- 历史状态提示

### 下载确认主链

- `app/services/add_to_downloader.py`
- `app/services/add_pending_context.py`

当前已支持：

- pending approval
- `confirm`
- 下载器 dispatch
- download monitor 登记

## 4. 核心判断

这轮不应该试图“一口气补完成人 BT 全套设想”。正确做法是只做最小 wedge：

### 最小 wedge

1. 成人查询能稳定给出可读结果
2. 结果里能清楚看出：番号、来源、历史状态、优先候选
3. 用户能稳定走确认下载
4. 下载完成后能自动归档
5. 保留期到点后能清理源资源

### 暂时不追求

- 大图卡片
- 全站点全量补图
- 批量页范围 / 批量补片
- 多渠道 richer reply 一起做
- 非 Telegram 宿主解耦
- 配置系统重构
- 再开一轮 services 结构总清洗

## 5. 方案对比

### 方案 A：成人 BT 最小闭环先做穿

摘要：先把成人 BT 做成一条从搜索到归档的可验证闭环，优先拿用户可见成果。  
工作量：M  
风险：中  
优点：

- 最快产出可演示结果
- 复用现有 registry / archive / approval 地基
- 能阻止项目继续沉没在结构清理里

缺点：

- 文档 gate 和少量基础债仍要顺手先修
- 不是最终体验形态，后面还要再补展示层

### 方案 B：先修平台基础，再回头做成人 BT

摘要：先做 docs gate、配置解耦、宿主解耦，之后再补成人 BT。  
工作量：L  
风险：中  
优点：

- 基础更干净
- 后续多线扩展更顺

缺点：

- 这轮几乎没有用户可见成果
- 非常容易继续烧 token 而没有“做成了一条线”的感觉

### 方案 C：继续 services 层结构降本

摘要：延续最近的主线，继续合并单消费者 helper、状态壳和重复结构。  
工作量：M 到无限  
风险：低  
优点：

- diff 可控
- focused tests 经验已经形成

缺点：

- 用户几乎感知不到收益
- 没有明确终点
- 已经验证过这条线会持续吞掉注意力

## 6. 推荐方案

**推荐：方案 A。**

原因很简单：当前项目最缺的是“结果面”，不是“再一轮内部整理”。这轮应该先拿到一条能看见、能验证、能讲清楚的成人 BT 闭环。

## 7. 这轮明确不做

- 不重构 `ExecutionGate`
- 不改 SQLite schema
- 不改 PT 主链语义
- 不改 movie-first 导入后半段
- 不做 Web UI / 桌面端
- 不做成人 BT 图片大卡片第一版
- 不做批量页范围、页抓取平台化、站点规则 DSL
- 不做 Feishu / WeCom / personal WeChat 的 richer reply 协同升级
- 不把 `services` 降本继续当单独主线

## 8. 实施分期

### Phase 0：施工前收口
预计：0.5 天

目标：

- 修复当前 docs gate 阻断
- 冻结这轮 scope
- 明确 focused 验证入口

要做：

- 处理 `AGENTS.md` 与 `docs/INDEX.md` 入口约定不一致
- 处理 `docs/*.md <= 15` 与当前基础文档数量冲突
- 把这份文档作为本轮唯一主线说明

完成标准：

- 文档约定不再阻塞后续连续施工
- 本轮 `NOT in scope` 不再变化

### Phase 1：成人搜索与只读结果收口
预计：1 到 2 天

目标：

- 让成人查询结果更像产品入口，而不是调试输出

要做：

- 明确成人查询入口和推荐使用方式
- 收口来源优先级与排序策略
- 强化 exact-id / helper / 历史提示的一致展示
- 给用户一个稳定的“选哪个”的文本心智模型

优先文件：

- `app/services/search_media.py`
- `app/services/bt_read_only_display.py`
- `app/services/search_reply_formatter.py`
- `tests/test_search_media.py`
- `tests/test_bt_read_only_display.py`

完成标准：

- 对典型 adult query，结果顺序和展示字段稳定
- 历史状态能明确提示“已有待确认 / 正在下载 / 已归档 / 已清理”

### Phase 2：确认下载路径收口
预计：1 到 2 天

目标：

- 从 adult result 到 pending add / confirm download 这一段稳定可用

要做：

- 检查 adult source -> `PendingAddContext` 的字段完整性
- 收口 adult 历史状态在 pending approval 阶段的表现
- 确认 direct magnet 走成人链时的下载确认体验

优先文件：

- `app/services/add_pending_context.py`
- `app/services/add_to_downloader.py`
- `app/bot/private_chat_bt_processing_runtime.py`
- `tests/test_add_pending_context.py`
- `tests/test_add_to_downloader.py`
- `tests/test_private_chat_runtime.py`

完成标准：

- 成人候选和成人磁力都能稳定走到 pending approval
- `confirm` 后下载器 dispatch 与 registry 状态一致

### Phase 3：归档与保留期闭环
预计：1 到 2 天

目标：

- 下载完成后的成人资源能自动归档，并在到期后清理

要做：

- 校验 `PostDownloadAutoImportService` 与 `AdultArchiveService` 的串联
- 校验 archive target、retention elapsed、source cleanup 语义
- 让失败路径也有明确日志与用户可读结果

优先文件：

- `app/services/post_download_auto_import.py`
- `app/services/adult_archive_service.py`
- `app/db/adult_content_registry_repo.py`
- `tests/test_adult_archive_service.py`
- `tests/test_post_download_auto_import.py`（若无则补 focused tests 到现有文件）

完成标准：

- 下载完成 -> 归档 -> registry 更新
- retention 到期 -> 删除下载器任务和源资源 -> registry 更新

### Phase 4：收尾验证与文档同步
预计：0.5 到 1 天

目标：

- 把“可用”变成“可复验”

要做：

- focused tests
- `make verify-mainline`
- docs 同步
- 记录 real smoke / 已知限制

完成标准：

- 本轮 focused gate 全绿
- 主线说明、已知限制、验证入口一致

## 9. 预计周期

### 保守估计

- Phase 0：0.5 天
- Phase 1：1.5 天
- Phase 2：1.5 天
- Phase 3：1.5 天
- Phase 4：0.5 天

**合计：约 5.5 天**

### 快一点的情况

如果 Phase 1 和 Phase 2 大量复用现有逻辑，**3 到 4 天**能拿到第一版可见成果。

### 慢一点的情况

如果成人查询、helper、archive 后半段暴露出真实协议缺口，**6 到 7 天**也还是合理，但超过这个长度就要重新砍 scope。

## 10. 验证策略

### focused tests

- 成人查询与排序
- adult history text
- pending add context
- downloader approval / confirm
- adult archive success / failure / retention cleanup

### repo-level gates

- `make quality`
- `make verify-mainline`

### smoke

至少要证明一条完整路径：

1. 发起成人查询
2. 得到可读结果
3. 创建待确认下载
4. `confirm`
5. 下载完成
6. 自动归档
7. 到期后清理

## 11. Superpowers 执行方式

这轮**不要**直接让 Superpowers 自由探索执行。正确顺序应该是：

1. 用这份文档做输入
2. 先跑 `/writing-plans`
3. 产出 task-by-task 的执行计划
4. 再跑 `/executing-plans`

原因：

- 这轮 scope 必须锁死
- 必须强制 `NOT in scope`
- 必须避免又回到“顺手继续 services 降本”的惯性

## 12. 执行时的硬约束

- 每轮最多一个最小闭环
- 每轮必须有 focused tests
- 不得顺手切到平台工程
- 不得把图片卡片和体验层扩成新主线
- 如果某一步需要改协议或 schema，必须停下来重新评审

## 13. Done 定义

当且仅当下面 6 条同时满足，这轮才算完成：

1. 成人查询结果可读、可解释、可排序
2. 成人候选可稳定走到 pending approval
3. `confirm` 后下载器 dispatch 与 registry 状态一致
4. 下载完成后能自动归档
5. retention 到期后能清理源资源
6. focused tests + 主线 gate 可复验

---

## 给 Superpowers 的一句话

> 当前唯一主线是“成人 BT 最小可用闭环”，不是平台重构，不是继续 services 总清洗。先修 docs gate，再按“搜索与展示 -> 下载确认 -> 归档与保留期清理 -> 验证收尾”顺序推进；严格遵守 `NOT in scope`。
