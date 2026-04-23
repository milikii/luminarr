# Luminarr (v69)

Luminarr 是一个面向 **2–4 人自托管影视场景** 的垂直自动化 Harness。

代码里当前已实现 Telegram / personal WeChat / Feishu / WeCom 四个私聊入口，以及 Transmission / qBittorrent、Emby / Jellyfin / Plex 等路径；但当前**保守首版发布承诺矩阵**只先冻结为 `Telegram 私聊 + PT Transmission + Emby + movie-first 主链`。它**不是**通用 AI 助手、通用 Agent 平台或通用多渠道平台。

## 1. 先看这里

- 你**不会代码，只想继续推进项目**：看 `docs/HUMAN_START_HERE.md`
- 你**准备复制一句话让 AI 开工**：看 `docs/OPERATOR_RUNBOOK.md`
- 你**想把项目跑起来**：看 `docs/GETTING_STARTED.md`
- 你**想理解系统怎么工作**：看 `docs/ARCHITECTURE.md`
- 你**想知道当前主线和当前风险**：看 `docs/STATUS.md`、`docs/NEXT_STEP.md`
- 你**想知道哪些边界已经定死**：看 `docs/DECISIONS.md`

## 2. 它现在能做什么

- 当前首版承诺矩阵：Telegram 私聊 + PT Transmission + Emby + movie-first 主链
- 已实现能力继续保留：四个私聊入口共用一套 shared runtime、approval、`jobs` 和 SQLite 真相
- 媒体主链已覆盖：搜索、下载审批、确认投递、状态查询、导入审批、硬链接导入、metadata、字幕翻译、媒体库刷新
- BT 支线已覆盖：PT / BT 分流、processing-path inquiry、TMDB 关联、`raw_bt` 目录选择、BT 搜索与最小订阅基线
- 下载器支持 Transmission + qBittorrent；刷新支持 Emby / Jellyfin / Plex（按配置选择 provider）

## 3. 当前边界

- 只做单机、单进程、单实例的自托管影视自动化
- 只维护一套业务真相，不为四个渠道各写一份业务协议
- 不做 Web UI、桌面端、Redis / MQ / PostgreSQL、多机分布式
- 不把项目扩成通用 AI / 插件 / MCP 平台

## 4. 当前健康度怎么看

- 当前短快照只看 `docs/STATUS.md`
- 当前唯一施工主线只看 `docs/NEXT_STEP.md`
- 当前默认继续施工已不是“收尾发布准备”，而是 **搜索相关性优化**
- 快速仓库质量入口：`make quality`
- 当前主线 focused 验证入口：`make verify-mainline`
- 仓库级 CI 入口：GitHub Actions `Quality` workflow 在 `push` / `pull_request` / `workflow_dispatch` 上运行 `make quality` + `make verify-mainline`
- 长期工程闭环和旧主线细节：按 `docs/INDEX.md` 分流去对应台账，不要从 README 开始翻历史

## 5. 如果你不会代码

默认直接用这一句：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```

当前保守版发布准备已经收口完成；现在默认继续推进，会自动落到 `docs/NEXT_STEP.md` 里的**搜索相关性优化**主线。
只有当文档真相、发布矩阵、真实 smoke 或质量入口再次漂移时，才需要回到 `docs/OPERATOR_RUNBOOK.md` 里的“收尾发布准备”模板。
如果你只想让 AI 先做冷启动检查或只收口文档，也不要自己手改长提示词，直接去 `docs/OPERATOR_RUNBOOK.md` 复制对应模板。

## 6. 文档入口

- `docs/HUMAN_START_HERE.md`：非技术操作者总入口
- `docs/OPERATOR_RUNBOOK.md`：可直接复制给 AI 的短模板
- `docs/INDEX.md`：按身份分流的文档地图
- `docs/GETTING_STARTED.md`：安装、启动、最小 smoke
- `docs/ARCHITECTURE.md`：系统结构说明
- `docs/STATUS.md`：当前短快照
- `docs/NEXT_STEP.md`：当前唯一主线
- `docs/DECISIONS.md`：长期边界
