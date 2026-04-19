# docs/DECISIONS.md (v54)

> 目的：只保留“当前仍然有效”的项目决策。
> 说明：旧的阶段推进记录、历史 next-step 迁移、旧验收备注已清理。
> 当前施工目标只看 `docs/NEXT_STEP.md`；当前实现状态只看 `docs/STATUS.md`；项目来龙去脉看 `docs/HISTORY.md`。

---

## D-001 项目定位
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  - Luminarr 只做 2–4 人自托管影视场景的垂直自动化 Harness。
  - 当前主线只服务“搜索 -> 下载 -> 入库 -> 刷新 -> 状态查询 -> 追更”。
  - 不做通用 AI 助手、通用办公自动化、通用 Agent 平台。
- **原因**：
  保持边界窄，才能长期稳定维护。

## D-002 交互模型
- **状态**：已决定
- **日期**：2026-04-01
- **结论**：
  - 用户侧保持自然语言。
  - 系统内部必须转成结构化意图、确定性路由和显式副作用执行。
  - 自然语言体验不等于模型自由发挥。
- **原因**：
  用户要的是“像聊天”，系统需要的是“可控执行”。

## D-003 当前固定运行画像
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  当前主线固定为：
  - Telegram + personal WeChat + Feishu + WeCom（当前为最小私聊文本基线）
  - TMDB
  - Prowlarr（当前主来源）+ 最小 BT WebSource（仅 BT 支线）
  - Transmission + qBittorrent
  - Emby / Jellyfin / Plex（按 `MEDIA_SERVER_PROVIDER` 选择 refresh provider）
  - SQLite
  - Docker Compose
  - 单实例 / 单进程 / 单机
  - movie-first workflow
- **原因**：
  主线必须先固定，才能避免路线漂移。

## D-004 文档优先级
- **状态**：已决定
- **日期**：2026-04-02
- **结论**：
  文档冲突时按以下顺序解释：
  1. `docs/DECISIONS.md`
  2. `docs/NEXT_STEP.md`
  3. `docs/STATUS.md`
  4. `README.md`
  5. `AGENTS.md`
- **原因**：
  防止新旧文档互相打架。

## D-005 PT / BT 主干边界
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - PT 主干承接正常观影需求，例如：
    - `我想看 X`
    - `追更 X`
    - `watchlist`
  - BT 主干承接直接 BT 需求，例如：
    - 原始 `magnet:?`
    - 明确“下载这个 BT / 下载这个磁力”
  - 分叉点必须在 parser / routing 入口，而不是到了后半段再临时判断。
  - PT 与 BT 从入口开始天然隔离。
- **原因**：
  两条链的目标不同，混在一起只会让代码和交互都失控。

## D-006 模型使用边界
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - parser-first，LLM-fallback。
  - 模型不负责：
    - 幂等
    - lease ownership
    - execution-result truth
    - approval re-validation
  - 背景恢复和 scheduler tick 不得依赖 LLM 调用。
  - 高歧义搜索允许只读探索辅助，但不得写主 workflow 真相或触发副作用。
- **原因**：
  模型适合辅助理解，不适合做账本和红绿灯。

## D-007 执行安全边界
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - `telegram_updates` 是 Telegram 去重真相源。
  - `jobs.version + lease_owner + lease_until` 是当前执行所有权真相源。
  - `confirm <id/hash>` 必须从持久化 `job + approval_record` 重建最小执行上下文。
  - 只读动作可标记 `concurrency_safe`；副作用路径必须串行。
  - 同一 job 的副作用不得并发；未持有 lease 时必须退出。
- **原因**：
  先保住副作用安全，再谈自动化提速。

## D-008 审批与导入纪律
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - `add_to_downloader` 和 `import_to_library` 都必须先进入 pending approval。
  - `approval_record` 维护 pending / approved / expired 的最小真相，并带 `lease_version / executed_version / expires_at`。
  - 重复、过期、stale `confirm` 必须确定性拒绝。
  - confirmed import 默认先走硬链接；跨文件系统失败时必须进入显式 copy-fallback pending，不得静默复制。
- **原因**：
  下载和导入都属于会改文件、改下载器状态的动作，必须有同样严格的闸门。

## D-009 当前媒体后半段
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - confirmed import success 后，当前媒体后半段固定为：
    - 规范化命名
    - metadata scraping（TMDB + Fanart.tv）
    - subtitle auto-translation（当前仅 `.srt`）
    - 媒体服务器 refresh（Emby / Jellyfin / Plex）
  - refresh 失败不回滚 import success。
  - metadata / subtitle 失败必须显式记录并打印可读错误，但不回滚 confirmed import success。
- **原因**：
  入库成功是真相；刮削、字幕、刷新是后续增强动作。

## D-010 BT 分类后的后半段
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - BT 必须先做分类：`movie / series / anime / raw_bt`。
  - `movie / series / anime` 属于媒体型 BT：
    - 必须尝试做 TMDB 关联
    - 下载完成后复用现有媒体后半段
  - `raw_bt` 属于原始 BT：
    - 不做 TMDB
    - 不做 metadata / subtitle / refresh
    - 只允许走预设目录选择 -> 下载 -> 放置
    - 手动 `import <id/hash>` 必须确定性拒绝
- **原因**：
  媒体型 BT 和原始 BT 是两类完全不同的落地方式。

## D-011 下载器模型
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 下载器采用“实例 + 角色绑定”：
    - 配置定义多个实例
    - `pt_downloader` / `bt_downloader` 绑定实例名
  - 任务真相必须记住：
    - 当前任务是 PT 还是 BT
    - 当前任务类型是 `movie / series / anime / raw_bt`
    - 实际投递到哪个下载器实例
    - 该实例属于哪种协议
  - qBittorrent 当前已落地最小协议：
    - add torrent / magnet
    - get status
    - get import source
- **原因**：
  角色和实例分开，后面才不会因为换下载器就重写整条业务链。

## D-012 watchlist 与 BT subscription 当前边界
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - `watchlist` 当前是手动、持久化、无副作用基线。
  - `watchlist` 支持 `movie / series / anime`，但不做 auto-download。
  - `btsub` 当前已支持手动命令和最小后台 tick。
  - `btsub` 命中新资源后，仍必须走现有 downloader approval -> `confirm` 边界。
  - 当前不允许：
    - 自动 `confirm`
    - `raw_bt` subscription
    - 通用 scheduler 平台化
- **原因**：
  先让追更和订阅可控，再考虑更重的自动化。

## D-013 当前明确不做
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  当前主线不做：
  - personal WeChat 群聊、图片、文件、卡片、按钮、多账号编排
  - Feishu / WeCom 群聊、图片、卡片、按钮回调、通用多渠道平台化
  - Jellyfin / Plex 全量媒体管理能力对齐
  - 通用 plugin / skill / MCP 平台化
  - React TUI / Web UI / 桌面端
  - Redis / MQ / PostgreSQL
  - 多机分布式部署
- **原因**：
  这些方向都会把项目从“可控自动化链”拉成“大平台”。

## D-014 BT 外部网站源
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 当前 BT 主干已在 Prowlarr 之外接入最小 `WebSource` baseline。
  - `WebSource` 只允许服务 BT 分流：
    - 直接 BT / magnet 搜索
    - BT 订阅 / 连续下载
    - BT 手动探索
  - `WebSource` 不得进入 PT 主链。
  - `Prowlarr + WebSource` 必须先经过共享 BT 来源适配层，再进入 BT 链路。
  - 外部网站源命中结果后，仍必须复用现有 downloader approval -> `confirm` -> dispatch 边界。
  - 第一阶段只允许静态 HTML + 直接 magnet / torrent 链接。
  - 第一阶段不接入 JS 渲染、CAPTCHA、强登录站。
- **原因**：
  BT 分流确实需要 Prowlarr 之外的资源来源，但不能反过来破坏 PT 主线。

## D-015 BT 站点规则定义与 BT-only read-only helper
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 外部 BT 网站源采用“项目内确定性站点规则定义”，不做通用 skill 平台。
  - 运行时主链仍由确定性代码负责：
    - 发请求
    - 解析页面
    - 统一候选字段
    - 校验链接
    - 去重
    - 进入既有审批链
  - 后续允许增加 BT-only read-only helper，用于：
    - 手动 BT 探索
    - 站点规则维护 / 修复辅助
    - HTML 到结构化候选的只读整理辅助
  - 该 helper 只允许存在于 BT 支线，且不得：
    - 写数据库
    - 写 approval / jobs / lease 真相
    - 直接 dispatch 下载器
    - 直接触发 import / refresh / 任何副作用
  - scheduler tick、`btsub run`、恢复逻辑不得依赖该 helper 或 LLM。
- **原因**：
  这里允许的是“BT 支线助手”，不是“通用 skill 平台”。

## D-016 本地集成验证基线
- **状态**：已决定
- **日期**：2026-04-03
- **结论**：
  - WSL Docker 的 Transmission + Emby 测试栈是正式本地集成验证基线。
  - `docs/TEST_ENV.md` 是该测试栈正式入口。
  - 涉及 `add_to_downloader` / `import_to_library` / `refresh_media_server` / 相关持久化协议的端到端任务，不得只靠 mock。
- **原因**：
  硬链接、下载器 RPC、媒体库刷新都要靠真实文件系统和真实接口验证。

## D-017 原始磁力入口后续增加“处理链”问询，而不是重新问协议类型
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 当用户直接发送 `magnet:?` 或明确要求“下载这个 BT / 磁力”时，系统仍先进入 BT 支线。
  - 当前该入口已增加一层最小问询，问的不是“PT 还是 BT”，而是：
    - `影视入库链`
    - `纯 BT 下载链`
  - 当用户选择 `影视入库链` 时：
    - 后续继续进入媒体型 BT 流程
    - 继续做 `movie / series / anime` 分类、TMDB 关联和媒体后半段
  - 当用户选择 `纯 BT 下载链` 时：
    - 后续继续进入 `raw_bt` / 纯 BT 流程
    - 不进入 TMDB、metadata、subtitle、refresh 链
  - 为兼容旧 follow-up，当前仍允许在该问询阶段直接回复：
    - `movie / series / anime`
    - `raw_bt`
- **原因**：
  用户已经发的是 BT 资源；这里真正需要区分的是后续处理链，而不是把协议类型再问一遍。

## D-018 仓库知识布局先优化“知识入口”，不先重命名代码目录
- **状态**：已决定
- **日期**：2026-04-06
- **结论**：
  - `README.md` 负责项目入口。
  - `docs/INDEX.md` 负责文档地图。
  - `docs/ARCHITECTURE.md` 负责解释系统怎么运作。
  - `docs/GETTING_STARTED.md` 负责从零到跑通。
  - `docs/NEXT_STEP.md` 只负责当前目标。
  - `docs/STATUS.md` 只负责当前快照。
  - `docs/CLEANUP_VERIFICATION_WINDOW.md` 继续负责 cleanup 验证窗口的详细台账。
  - `AGENTS.md` 负责给 AI 的执行规则和读文档入口。
  - 同一条事实尽量只写一处；其他文档优先跳转，不复制粘贴。
  - 当前阶段不重命名 `app/` 目录层级，不做“为了看起来更标准”而搬代码。
- **原因**：
  当前瓶颈是知识入口、协作效率和文档漂移，不是代码目录名字本身。

## D-019 仓库同时提供“本地 Python”与“最小 Docker Compose”两条启动入口
- **状态**：已决定
- **日期**：2026-04-06
- **结论**：
  - 仓库继续保留本地 Python 启动入口：
    - `.venv`
    - `.env.example`
    - `set -a && . ./.env && set +a && .venv/bin/python -m app.main`
  - 仓库新增最小容器入口：
    - `Dockerfile`
    - `docker-compose.yml`
  - `Makefile` 只作为命令缩写入口，不是唯一入口；即使系统里没有 `make`，仓库也必须还能按直接命令运行。
  - 当前应用本身不自动读取 `.env`；环境变量由 shell 或 `docker compose` 注入。
  - 容器入口继续保持最小，不把 Transmission / Emby / Prowlarr 一起内置进主 compose；这些依赖仍按现有外部服务或 `docs/TEST_ENV.md` 说明接入。
- **原因**：
  你当前主要依赖 Codex 推进，但最终仍需要一个人类能实际启动和验证的最小入口；同时仓库不应该因为缺少 `make` 而无法使用。
  这只是兼容捷径，不是新的主交互形状。

## D-020 纯 BT 下载链按单片资源优选，不复用影视资源规则
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - 纯 BT 下载链不复用影视入库链的复杂规则。
  - 当前纯 BT 使用场景以单片资源为主，因此后续优选只需要围绕“单个资源规格是否足够出色”来做。
  - 纯 BT 优选后续可采用“确定性预过滤 + LLM 辅助优选”的形状：
    - 代码先做基础过滤：
      - 链接有效
      - 非重复
      - 标题命中
      - 单片资源基本条件成立
    - 再允许 LLM 在少量候选中做“哪个版本更值得下”的辅助判断
    - 最终是否投递，仍由项目自己的确定性代码决定
  - 纯 BT 连续任务允许后续扩展为“批量 / 区间 / 持续任务”，例如按编号范围持续补齐单片资源。
- **原因**：
  纯 BT 资源的目标不是做标准影视入库，而是选出一份更出色的单片版本。这里可以比影视主链更简单，但仍要保留可控边界。

## D-021 BT subscription 已采用共享确定性选源，不再盲拿第一个结果
- **状态**：已决定
- **日期**：2026-04-04
- **结论**：
  - `btsub run` 和后台 scheduler tick 必须共用同一个确定性选源 helper。
  - BT subscription 选源不再盲目拿“第一个可下载结果”。
  - 当前最小选源规则允许使用这些确定性信号：
    - 链接存在
    - 跳过 `last_seen_source`
    - 明确低质量标记过滤优先级
    - 标题里的基础分辨率信息
    - `seeders`
    - `size`
  - 当前这一步仍不是通用质量评分 / 规则引擎。
  - 命中结果后，仍必须复用现有 downloader approval -> `confirm` 边界。
- **原因**：
  先把 BT subscription 从“盲选第一个结果”收紧到可解释、可复用、无 LLM 依赖的最小确定性基线，再继续后续 BT 路线。

## D-022 pure BT 最小单片优选先落成确定性文本查询基线
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - pure BT 现阶段先只落地最小确定性单片优选基线，不引入额外多轮框架。
  - 当用户发送文本型直接 BT 请求，并显式带上查询词，例如：
    - `下载这个 BT Frieren S01E01`
    - `下载这个磁力 某作品 EP01`
    进入 `纯 BT 下载链` 并完成 `raw_bt` 目标目录选择后，系统允许：
    - 先用现有搜索源拿候选
    - 过滤无链接候选
    - 过滤标题不命中的候选
    - 过滤明显低质量候选
    - 过滤明显多集 / 合集 / 整季候选
    - 再用基础分辨率、`seeders`、`size` 做最小确定性排序
  - 命中后，仍必须复用现有 downloader approval -> `confirm` 边界。
  - direct `magnet:?` 的 pure BT 路径保持原样，不经过这层文本查询优选。
  - 这一步仍不进入 TMDB、metadata、subtitle、refresh，也不复用影视入库链规则。
- **原因**：
  先把 pure BT 的“文本型单片资源挑一个更像样的版本”补成最小可用基线，同时避免把媒体链规则、`btsub` 规则和新的站点接入混在同一步里。

## D-023 非 Telegram 私聊适配先做“渠道作用域整数 ID 投影”，不改现有真相表主键形状
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - 当前 `jobs / watchlist / bt_subscription / clarification / bt_pending / candidate_mapping / download_monitor` 这些真相边界继续保留现有整数 `chat_id / user_id` 形状。
  - 非 Telegram 私聊渠道如果拿到的是字符串会话标识或用户标识，必须先在适配层做**稳定、确定性、带渠道命名空间**的整数投影，再进入 shared private-chat text runtime 和既有 service。
  - 渠道名必须进入投影输入，避免不同渠道相同原始字符串发生撞号。
  - 原始外部标识只保留在渠道适配层，用于该渠道自己的回消息动作；不得把它直接塞进现有 SQLite 整数真相列。
- **原因**：
  这样能在不改审批、作业、候选缓存和持久化协议的前提下，先把 Feishu 私聊最小文本入口接进现有主链，保持 diff 最小且风险可控。

## D-024 Feishu 当前只做最小私聊文本 webhook + reply 闭环
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - Feishu 当前只接：
    - 私聊 `p2p`
    - 文本消息
    - 文本回复
  - Feishu 适配层当前负责：
    - webhook 请求入口
    - Feishu payload 解析
    - 调用 shared private-chat text runtime
    - 把 runtime 产出的文本回发到原 Feishu 会话
  - 现有 workflow / approval / jobs / lease / SQLite 真相边界保持不变。
  - 这一步不扩成：
    - 通用 webhook 总线
    - 通用多渠道平台
    - 群聊 / 卡片 / 按钮回调
  - webhook 事件验签作为下一刀单独补，不和这一步的最小收发闭环混在一起。
- **原因**：
  先把 Feishu 的“真实请求进来、文本能回去”补成最小闭环，再做安全加固，能把 diff 控制在最小范围内，也更容易验证 Telegram 主链不回退。

## D-025 Feishu 事件验签使用原始请求体 + timestamp + nonce + Encrypt Key，且不干扰 URL 验证
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - Feishu 非 `url_verification` webhook 请求在进入 shared private-chat text runtime 前，必须先做验签。
  - 当前最小验签输入固定为：
    - 原始 HTTP request body
    - `X-Lark-Request-Timestamp`
    - `X-Lark-Request-Nonce`
    - `X-Lark-Signature`
    - `FEISHU_ENCRYPT_KEY`
  - `url_verification` 仍按 Feishu challenge 原样返回，不走这层签名拒绝。
  - 缺失签名、签名不匹配、时间戳不是合法整数时，必须在适配层显式拒绝并打印中文日志，不得进入现有 workflow / service。
  - 当前这一步只做签名校验，不做消息体解密、不做群聊/卡片/按钮回调。
- **原因**：
  这一步的目标是先把 Feishu 请求来源校验补上，同时保持现有文本入站链最小改动；URL 验证和后续更重的加解密能力不应混在同一步里。

## D-026 WeCom 先补已解密私聊文本适配内核，私聊会话外部标识暂复用 `FromUserName`
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - WeCom 当前最小落地顺序拆成两层：
    - 先补“已解密 XML 私聊文本消息 -> shared private-chat text runtime”的适配内核
    - 再补 callback URL 校验、解密和文本回包外壳
  - WeCom 私聊当前若拿不到独立会话 ID，则先把 `FromUserName` 同时作为：
    - 私聊会话外部标识，用于投影现有整数 `chat_id`
    - 用户外部标识，用于投影现有整数 `user_id`
  - `chat_id` 和 `user_id` 虽然都来自 `FromUserName`，但仍必须经过现有 `channel + principal_kind + external_id` 投影，因此最终整数值仍保持分离。
  - `ToUserName`、`AgentID`、原始 XML 只保留在 WeCom 适配层，用于后续 callback 回包，不进入现有 SQLite 真相表。
  - callback 外壳当前最小实现固定为：
    - 用 `WECOM_TOKEN + timestamp + nonce + echostr/Encrypt` 做签名校验
    - 用 `WECOM_ENCODING_AES_KEY + WECOM_RECEIVE_ID` 做 AES 解密和回包加密
    - runtime 产出的文本通过 callback HTTP response 返回加密被动回复 XML
  - 当前不新增独立 WeCom 主动发消息客户端；最小文本回包只走 callback response。
- **原因**：
  先把 WeCom 的消息解析和 runtime 复用边界补稳，再单独接 callback 外壳，能把 diff 控制在最小范围，也能避免过早把渠道细节渗进既有持久化协议。

## D-027 personal WeChat 默认使用 `wechat-clawbot` Python 包作为渠道底座
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - 当前 personal WeChat 默认使用 `wechat-clawbot` Python 包作为当前项目的个人微信渠道底座。
  - 当前项目不把 npm 侧 ClawBot/OpenClaw 插件作为 personal WeChat 的主实现形态。
  - `wechat-clawbot` 在当前项目里的职责只限于提供个人微信所需的底层渠道能力，例如：
    - iLink API 客户端
    - QR 登录
    - 长轮询 `getUpdates`
    - `sendMessage`
    - 凭据持久化
  - Luminarr 自身仍负责：
    - 把 personal WeChat 外部标识压进现有 shared private-chat text runtime
    - 继续复用现有 workflow / approval / jobs / lease / SQLite 真相边界
  - 当前 personal WeChat 最小文本基线固定为：
    - 启动时读取 `wechat-clawbot` 已保存登录态
    - 只自动启动唯一可用账号
    - 用长轮询 `getUpdates` 收私聊文本
    - 把 runtime 产出的文本通过 `sendMessage` 回到原私聊
  - 若检测到多个已保存账号，则显式拒绝启动当前 personal WeChat 文本服务，不做多账号编排。
  - 当前不要求在同一进程里于 QR 登录成功后热启动 personal WeChat 文本轮询；已保存登录态在下次启动时生效即可。
  - 后续若把通知系统接到 personal WeChat，主动推送必须依赖 `wechat-clawbot` 提供的有效 `context_token`。
  - 一旦 `context_token` 过期或缺失，personal WeChat 主动推送只能降级到 Telegram / 其他渠道，而不能静默当作成功。
- **原因**：
  当前主仓库是 Python 主体，后续 personal WeChat 直接复用 `wechat-clawbot` 更贴合现有运行时；这样能避免把渠道适配做成额外的 Node sidecar，也能继续保持“渠道适配薄、业务主链不分叉”的结构。

## D-028 personal WeChat 二维码登录先依赖 Telegram 图片发送基线，卡片 UI 不是硬前置
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - personal WeChat 当前预定的最小登录路径是：
    - 管理员先在 Telegram 触发 personal WeChat 登录
    - Luminarr 通过 `wechat-clawbot` 取到登录二维码
    - Luminarr 先把二维码图片或文件发到 Telegram 私聊
    - 管理员再用手机微信扫码完成登录
  - 因此，在 personal WeChat 进入正式施工前，Telegram 必须先具备最小图片/文件发送能力。
  - Telegram richer card/UI polish 不是 personal WeChat 登录闭环的硬前置；登录最小闭环只要求能发二维码和状态文本。
  - 这一步仍不把 Telegram 扩成通用富媒体 UI 平台，只补 personal WeChat 登录所需的最小媒资回传能力。
- **原因**：
  个人微信二维码登录必须先把二维码可靠地交给管理员；先补 Telegram 图片发送能力，可以把 personal WeChat 的接入拆成更小、更清晰的闭环，同时避免让卡片 UI 优化变成不必要的阻塞项。

## D-029 媒体型 BT 与后续追更必须预留独立名称解析步骤
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - 当前 movie-first PT 主链保持不变：
    - 用户先发 `片名 [年份]`
    - `search_media` 先做 `片名 / 年份` 解析
    - 再去 TMDB 查媒体对象
    - 再拿 TMDB 标题去搜索来源
  - 但后续只要进入这些场景：
    - 媒体型 BT 的标题关联
    - `series / anime` 追更
    - 下载完成后的文件归集与匹配
    就必须在 TMDB 关联或后处理前，先经过一个**独立名称解析步骤**。
  - 该步骤接收的输入可以是：
    - 搜索结果标题
    - 下载器任务名
    - 实际文件名
  - 该步骤输出的最小结构化结果必须至少包含：
    - `title`
    - `year`
    - `season`
    - `episode`
    - `quality_tags`
  - 该步骤在实现时可以借鉴 MoviePilot 的 case、路径预处理和名称规范化思路，但当前实现只收最小子集，不直接搬整套规则引擎。
  - 名称解析必须坚持 parser-first，优先使用确定性规则；后续允许增加项目内可配置的小型识别词 / 替换规则，用来处理动漫、国产剧和站点命名偏移，但当前不引入复杂 DSL。
  - `series / anime` 真正落地时，必须同步评估 `.ass` 字幕支持；不要把动漫字幕主流格式问题继续后拖。
  - 当前这条先作为后续设计约束写入，不在本 step 直接启动实现。
- **原因**：
  用户输入的片名、来源里的 torrent 标题、下载完成后的文件名，不是同一种文本。若系统不能先把这些文本收敛成统一结构，TMDB 关联、追更、自动导入匹配就会越来越脆，尤其是 `series / anime`。

## D-030 BT 选源后续升级为共享确定性评分器，不直接引入 DSL
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - 当前 `pure_bt` 与 `BT subscription` 已有最小确定性选源，不再把系统描述成“只有黑名单”。
  - 后续要补的不是一套复杂规则语言，而是一个**共享确定性评分器**：
    - `pure_bt`
    - `manage_bt_subscription`
    - 后续媒体型 BT 选源
    尽量共用同一套候选评分 helper。
  - 共享评分器的输入必须来自现有 BT 来源适配后的统一候选字段；评分前仍先做确定性预过滤，例如：
    - 链接存在
    - 标题基本命中
    - 去重
    - 低质量版本过滤
  - 当前允许优先使用的评分信号包括：
    - 分辨率
    - `seeders`
    - `size`
    - 基础来源类型标记
  - 只有等共享候选字段稳定补齐后，才继续把这些信号扩到：
    - 字幕
    - 片源
    - 制作组
    - 其他用户偏好
  - 配置形状优先采用显式权重 / 小型配置，不先引入 DSL。
  - 当前这条先作为后续设计约束写入，不在本 step 改现有 BT shared source adapter、`btsub` 或 pure BT 选源实现。
- **原因**：
  系统真正需要的是“面对多个候选时，能稳定、可解释地选一个”，不是先发明一门规则语言。先把评分器做成共享、确定性的，后面字段 richer 了再逐步加权，风险更低。

## D-031 `job_event` 先做持久化事件账本，旁路 dispatcher 后续单独消费
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - `job_event` 当前和后续的第一职责，都是把已经发生的业务事实按顺序写进 SQLite 真相账本。
  - 主流程里的 service，例如：
    - `add_to_downloader`
    - `get_download_status`
    - `import_to_library`
    只负责在对应动作完成后追加 `job_event`，不把通知、统计、清理同步这些旁路动作重新耦回主链。
  - 后续如果要补事件 dispatcher，应采用“单独消费者”形状：
    - dispatcher 从 `job_event` 里按递增 `id` 读取新事件
    - dispatcher 再决定要不要发通知、记统计、做清理同步
  - dispatcher 失败时，只记录显式中文错误日志和处理建议，不影响已经提交的主流程事实。
  - 当前这条先作为后续设计约束写入，不在本 step 直接新增通知系统、统计系统或 cleanup 自动化。
- **原因**：
  主流程负责写真相，旁路能力负责消费真相。只有先把两者拆开，通知、统计、清理同步这些后续功能才不会重新反咬 downloader / import 主链的稳定性。

## D-032 四个渠道当前都是正式私聊入口，但只维护一套共享业务真相
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - Telegram、personal WeChat、Feishu、WeCom 当前都是正式入口，不把其中任何一个当成“演示渠道”或“次要渠道”。
  - 四个渠道必须共用同一套：
    - `shared private-chat text runtime`
    - workflow / approval / jobs / lease / SQLite 真相边界
  - 渠道适配层只负责：
    - 入站校验、验签、解密或轮询
    - 外部标识投影到既有 `chat_id / user_id`
    - 调用 shared runtime
    - 把文本或最小媒资发回原渠道
    - 必要的最小渠道特化展示
  - 新文本协议和新业务行为必须优先落在 shared runtime 或 service，再补各渠道适配层最小胶水和回归。
  - 渠道专属能力继续各自独立维护：
    - Telegram 最小图片/文件发送
    - personal WeChat 二维码登录与长轮询
    - Feishu webhook 验签
    - WeCom callback 验签、解密与加密回包
- **原因**：
  四个渠道都要真用，但业务真相不能维护四份。共享 runtime 才能同时保住一致性和维护成本。

## D-033 cleanup 当前进入“有退出条件的验证窗口”，不做无限期观察
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - 已落地的 cleanup inspect / discoverability / execution / rejection guidance / success follow-up / failure observability 当前视为稳定基线。
  - cleanup 下一步不是继续无限观察，而是进入一个明确的验证窗口：
    - 以四渠道真实私聊使用为准
    - 保持现有 cleanup 文本协议、guardrail、删除范围不变
    - 只允许修回归、补显式可观测性，不新增 cleanup workflow
  - cleanup 窗口结束前必须把 PT 下载 `pt_min_seed_hours` / 做种保护缺口记录清楚；若现有 guardrail 还没覆盖下载器侧做种状态，就不得把“删除做种资产”视为已验证稳定能力。
  - cleanup 验证窗口的退出条件固定为：
    - 完成一个明确的真实使用周期
    - 四个渠道都确认过“消息进来 -> shared runtime -> 文本回去”的最小闭环
    - cleanup 协议没有回退
  - 当前验证窗口的具体起止日期和四渠道 smoke 证据，统一记录在 `docs/CLEANUP_VERIFICATION_WINDOW.md`；`docs/STATUS.md` 只保留窗口快照。
  - 一旦退出条件满足，后续主线应推进到更高用户价值的能力，不再把 cleanup 观察无限延长。
- **原因**：
  没有退出条件的观察会持续消耗注意力，却不持续增加用户价值。

## D-034 文档按“决策 / 施工 / 现状 / 入口”分层，不重复堆叠同一事实
- **状态**：已决定
- **日期**：2026-04-05
- **结论**：
  - `docs/DECISIONS.md` 只保留当前仍有效的长期规则和边界。
  - `docs/NEXT_STEP.md` 只保留当前唯一施工路径、明确退出条件和本 step 的禁止项。
  - `docs/STATUS.md` 只保留当前实现真相、主要风险和最新验证快照，不再堆完整历史流水。
  - 对应主线的 log 或 blueprint 承接当前主线的详细闭环、focused tests 和 commit 轨迹（当前为 `docs/SERIES_ANIME_NAMING_PLAN.md` + `docs/SERIES_ANIME_NAMING_LOG.md`）；更早完成的持久化收口细节继续保留在 `docs/PERSISTENCE_CLOSURE_LOG.md`，避免把 `docs/STATUS.md` 重新写胖。
  - `README.md` 只保留项目定位、当前结构、能力概览和当前路线，作为仓库入口；cleanup 窗口的详细证据仍收口到 `docs/CLEANUP_VERIFICATION_WINDOW.md`，当前主线的详细收口台账收口到对应主线 log / plan（当前为 `docs/SERIES_ANIME_NAMING_PLAN.md` + `docs/SERIES_ANIME_NAMING_LOG.md`）。
  - `AGENTS.md` 负责把以上主线同步给编码代理，但不是当前执行真相的首要来源。
  - 阶段演进和历史验证若需要保留，放到 `docs/HISTORY.md`，不再反向污染当前文档。
- **原因**：
  文档的作用是降低决策成本。分层不清、反复展开同一事实，会让文档本身变成新的维护负担。

## D-035 项目交付形态继续以私聊 bot 为主，体验增强优先走渠道内 richer reply
- **状态**：已决定
- **日期**：2026-04-06
- **结论**：
  - 当前和后续的主交付形态，继续保持为 Telegram / personal WeChat / Feishu / WeCom 私聊 bot。
  - 用户体验增强优先补在渠道回包层，例如：
    - 更清晰的文本分段和字符排版
    - 图片 / 文件回传
    - 最小信息卡片或富文本展示
  - 这些体验增强仍必须复用现有 shared private-chat text runtime、workflow、approval、`jobs` 和 SQLite 真相，不得为展示层再长出第二套业务分支。
  - 当前不把 Web UI / 桌面端当成主交付方向；需要提升可用性时，先把私聊 bot 体验和人类可读文档补好。
- **原因**：
  这个项目的核心价值是“人在私聊里发一句话就能完成任务”。若为了解决体验问题而转去做另一套 UI 主线，会打散当前已经建立起来的 shared runtime 和审批边界。

## D-036 shared private-chat runtime 必须真正 channel-agnostic，不再反向依赖 Telegram context
- **状态**：已决定
- **日期**：2026-04-14
- **结论**：
  - shared runtime 必须是独立的通用入口，不再通过伪造 `SimpleNamespace(application.bot_data=...)` 去调用 Telegram 专用函数。
  - Telegram / personal WeChat / Feishu / WeCom 四个渠道都只能把：
    - `query`
    - `reply_func`
    - `chat_id / user_id`
    - shared services / bot_data / injected capability
    这些通用参数传进 shared runtime。
  - `微信登录`、Telegram 图片/文件发送这类渠道专属能力，必须改成显式注入项；不能继续靠 shared runtime 反向读取 `context.application.bot`。
- **原因**：
  共享 runtime 的目标是“四渠道共用一套业务真相”，不是“让非 Telegram 渠道伪装成 Telegram”。继续反向依赖 Telegram context，会把一个渠道改动放大成四渠道同时回归。

## D-037 下载器路由与状态查询必须 fail-closed，不允许静默回退默认下载器
- **状态**：已决定
- **日期**：2026-04-14
- **结论**：
  - `downloader_name`、任务身份或渠道身份解析失败时，必须显式报错并打印中文日志；不得静默回退到默认 Transmission、默认实例名或共享整数 `0`。
  - `project_channel_chat_id` / `project_channel_user_id` 这类渠道身份投影 helper，遇到空输入时必须 fail-closed，而不是返回看起来合法的共享 ID。
  - `get_download_status` 当前会写 `download_monitor`、补 `downloader.completed_observed`，并可能接到 auto-import；因此它不是只读动作，不得放进 `READ_ONLY_ACTIONS` 绕过副作用串行边界。
- **原因**：
  “解析失败后偷偷走默认值”会把真实错误伪装成“查不到资源”或“查错下载器”，最难排查。状态查询既然会写真相，就必须继续按 stateful path 对待。

## D-038 主线兼容版 BT 批量任务只允许“确定性批量预览 + 显式批量确认”
- **状态**：已决定
- **日期**：2026-04-15
- **结论**：
  - 后续如果补 BT 批量任务，只允许走主线兼容版形状：
    - 用户自然语言
    - parser / routing 解析成结构化批量请求
    - `WebSource` / BT source adapter 做确定性抓取
    - 确定性代码完成编号范围过滤、去重、分页汇总、基础排序
    - 系统回批量预览或批量待确认文本
    - 用户显式执行批量 `confirm`
    - 下载器 dispatch 继续复用既有 `approval -> confirm -> jobs -> job_event` 真相边界
  - 这条能力只允许落在 BT 支线，且优先服务 `raw_bt` / 纯 BT 下载链；不得把 PT 主链、媒体型 BT 入库链或既有 `watchlist` / `btsub` 边界一起放宽。
  - 站点接入仍必须是项目内确定性 `WebSource` 规则：
    - 明确 allowlist 站点
    - 明确页面类型，例如用户页、列表页、编号范围页
    - 明确静态 HTML + 直接 magnet / torrent 链接边界
    - 不允许让 LLM 临时决定“去哪个未知站点抓什么页面”
  - LLM 在这条能力里最多只负责：
    - 把自然语言解析成结构化批量请求
    - 对批量预览结果做只读整理或摘要
    不得负责：
    - 自由抓站
    - 写 workflow / approval / jobs / lease 真相
    - 自动 `confirm`
    - 直接 dispatch 下载器
  - 这条能力也不得包装成通用 plugin / skill / MCP 平台；成人站点或其他 BT 站点若要接入，仍共用同一套主线兼容边界，不存在“题材专项豁免自动 confirm”。
- **原因**：
  纯 BT 后续确实需要支持“用户页 / 编号范围 / 批量补齐”这类更强的操作，但当前项目的核心仍是“自然语言入口 + 确定性执行 + 可恢复真相”。若把 BT 批量任务做成 LLM 自由抓取和自动投递，会直接破坏既有 approval、recoverability 和主线边界。
