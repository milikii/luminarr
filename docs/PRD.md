# PRD.md

> 本文基于 2026-04-28 仓库代码、测试、配置和运行脚本反推得到，描述的是“当前已实现行为”，不是额外承诺的新需求。

## 1. 产品定义

Luminarr 是一个面向小规模自托管影视场景的私聊自动化系统。它把“找资源、选资源、确认下载、查询状态、确认入库、刷新媒体库、必要时清理下载源”收敛到同一条可追踪、可恢复、可审计的聊天式工作流里。

它不是通用 AI 助手，也不是通用多渠道机器人平台。当前代码体现出的产品核心是：

- 用私聊文本作为唯一主交互面
- 用显式 `confirm` 审批保护所有副作用
- 用 SQLite 保存任务、审批、事件和中间状态真相
- 用单进程把多渠道入口统一接到同一套业务链

## 2. 目标用户

- 维护自托管媒体库的个人或 2-4 人小团队操作者
- 已有或计划使用 Prowlarr、Transmission / qBittorrent、Emby / Jellyfin / Plex
- 能接受 Docker、环境变量、目录映射、硬链接等运维概念
- 希望在聊天工具里完成大部分操作，而不是频繁切换 Web UI

## 3. 要解决的问题

- 搜索、下载、入库、刷新分散在多个系统里，人工串联成本高
- 直接把自然语言接到副作用操作风险太高，需要审批和恢复边界
- 多渠道入口容易造成四套业务逻辑分叉，维护成本高
- 下载完成后的后处理容易漏做，尤其是 metadata、字幕和媒体库刷新
- 清理下载源时容易误删，需要 import 关联和 guardrail

## 4. 核心价值

- 用户只需要记住少量自然语言命令和 `confirm` / `cancel`
- 系统内部保持确定性路由、持久化真相和 fail-closed 行为
- 下载、导入、cleanup 都有明确审批、事件记录和状态恢复路径
- 同一套 shared private-chat runtime 可复用到 Telegram、personal WeChat、Feishu、WeCom

## 5. 当前已实现的主要能力

### 5.1 搜索与选片

- 支持自然语言影视搜索，例如 `我想看 Dune 2021`
- 查询 Prowlarr 结果，并结合 TMDB 做标题、年份和媒体身份增强
- 对结果排序、去重、格式化展示
- 当结果过于歧义时，进入澄清状态而不是盲目返回候选
- 把候选持久化到 `candidate_mapping`，允许用户后续用数字序号选择

### 5.2 下载确认链

- 用户可通过候选序号、BT 批量选择、或直接磁力 / 链接创建待确认下载
- 下载不会立即执行，必须经过 `confirm <任务引用>`
- 下载确认状态写入 `approval_record` 和 `jobs`
- 实际投递支持 Transmission 和 qBittorrent
- 下载成功后会记录 job event，并登记到 `download_monitor`

### 5.3 状态查询与下载完成跟进

- 支持 `status <任务ID或Hash>` 查询下载器状态
- 会把状态观察写回 `download_monitor`
- 首次观察到完成时写入完成事件
- 可触发自动导入跟进，或对成人 BT 触发归档 / 保留期清理逻辑

### 5.4 入库确认链

- 支持 `import <任务ID或Hash>` 创建待确认导入
- raw BT 任务会被明确阻断，不进入媒体入库链
- 确认导入时默认走硬链接
- 跨文件系统会进入显式 `copy-fallback pending`，再次 `confirm` 才走复制
- 导入成功后会做 metadata scraping、字幕翻译、媒体库刷新

### 5.5 BT 支线

- 支持直接磁力 / BT 指令入口
- 直接磁力会先问处理链：影视入库链、成人 BT 归档链、pure BT 下载链
- 影视入库链会继续问 `movie / series / anime`，再做 TMDB 关联
- pure BT 会要求选择预设下载目录
- 成人 BT 会进入成人资源历史登记、完成后归档、到期后清理
- 支持 BT 只读搜索、批量预览、批量确认

### 5.6 清理下载源

- 支持 `cleanup inspect` 只读预检
- 支持 `cleanup` 实际删除下载源文件或目录
- cleanup 依赖 `import.succeeded` 事件里的 source / target 关联
- 具备路径保护、目标存在性检查、PT 最小做种窗口保护

### 5.7 持久化的轻量清单能力

- `watchlist`：手动维护想看清单，不自动下载
- `btsub`：维护 BT 订阅，支持手动运行和后台 scheduler tick
- 命中新资源后仍然走现有下载审批边界，不自动确认

### 5.8 多渠道私聊入口

- Telegram 文本私聊
- personal WeChat 私聊文本轮询
- Feishu 私聊文本长连接
- WeCom 私聊文本 webhook

这些入口共享同一套 shared private-chat runtime，而不是各写一套业务逻辑。

## 6. 产品边界

当前代码明确体现出的边界如下：

- 只做私聊文本，不做群聊协作
- 不提供 Web UI、桌面端或通用控制台
- 不做通用插件平台、通用 Agent 平台、通用办公自动化
- 不做多机分布式部署；运行画像是单机、单进程、单 SQLite
- 不对 raw BT 提供媒体导入能力
- 不对 watchlist 提供自动下载
- 不对 BT subscription 提供自动 `confirm`

## 7. 非功能要求

- 所有副作用路径都尽量 fail-closed
- 任务、审批、事件、候选、pending follow-up 都尽量持久化
- 回复文本要能适配不同渠道，但业务真相不能分叉
- 文档、测试、Makefile 和运行脚本共同构成当前行为边界

## 8. 当前外部依赖画像

- 搜索：Prowlarr + 可选 BT WebSource
- 元数据：TMDB + 可选 Fanart.tv
- 下载器：Transmission、qBittorrent
- 媒体库刷新：Emby、Jellyfin、Plex
- 渠道：Telegram、personal WeChat、Feishu、WeCom
- 本地工具：SQLite、Docker Compose、`ffmpeg` / `ffprobe`（字幕相关）

## 9. 当前明显限制

- 启动入口仍然以 Telegram Application 为宿主，其他渠道 sidecar 挂在其生命周期上
- `load_settings()` 仍把 `TELEGRAM_BOT_TOKEN`、`PROWLARR_*`、`TRANSMISSION_BASE_URL` 视为启动硬必填
- 超大 service 文件较多，维护重点仍然偏向“收口已有复杂度”而不是扩功能
