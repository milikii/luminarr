# docs/INDEX.md (v6)

> 目的：给人和 AI 一个统一的文档地图，先知道“哪份文档回答哪类问题”，再决定往哪里读。

## 1. 如果你是第一次接触这个仓库

按这个顺序读：

1. `README.md`
2. `docs/GETTING_STARTED.md`
3. `docs/ARCHITECTURE.md`
4. `docs/NEXT_STEP.md`
5. `docs/STATUS.md`
6. `docs/DECISIONS.md`

## 2. 每份文档负责什么

| 文档 | 负责回答的问题 | 真相类型 |
| --- | --- | --- |
| `README.md` | 这个项目是什么，适合谁，从哪里开始 | 项目入口 |
| `docs/GETTING_STARTED.md` | 一台新机器怎么把仓库跑起来 | bring-up 说明 |
| `docs/ARCHITECTURE.md` | 一条消息从哪里进、到哪里去、谁写数据库 | 结构说明 |
| `docs/NEXT_STEP.md` | 当前唯一主线是什么，不该顺手做什么 | 当前施工目标 |
| `docs/STATUS.md` | 当前已经落到哪里，最近一次验证结果是什么 | 当前快照 |
| `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md` | 当前 `import_to_library.py` 导入编排层瘦身 / 模块化主线的详细闭环、focused tests 和风险分组 | 当前主线台账 |
| `docs/TELEGRAM_BOT_SLIMMING_LOG.md` | 已完成的 `telegram_bot.py` 渠道层瘦身 / 模块化主线详细闭环、focused tests 和风险分组 | 已完成主线台账 |
| `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md` | 已完成的独立后台下载完成轮询回归与验证收口主线详细闭环、focused tests 和风险分组 | 已完成主线台账 |
| `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md` | 已完成的 Feishu 私聊事件解析器去重主线详细闭环、focused tests 和风险分组 | 已完成主线台账 |
| `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md` | 已完成的 Feishu 长连接私有 API 风险收口主线详细闭环、focused tests 和风险分组 | 已完成主线台账 |
| `docs/PERSISTENCE_CLOSURE_LOG.md` | 更早完成的持久化吞错收口主线详细闭环、focused tests 和 commit 轨迹 | 已完成主线台账 |
| `docs/DECISIONS.md` | 为什么这么做，哪些边界已经定死 | 长期决策 |
| `docs/CLEANUP_VERIFICATION_WINDOW.md` | cleanup 验证窗口的详细台账和证据 | 活动台账 |
| `docs/TEST_ENV.md` | 本地 Transmission / Emby 联调栈怎么检查 | 测试环境说明 |
| `docs/HISTORY.md` | 项目怎么演化到今天 | 历史背景 |
| `AGENTS.md` | 给 Codex 的仓库内执行规则和读文档入口 | AI 操作手册 |

## 3. 当前推荐读法

### 想理解“系统怎么动起来”

读：

1. `docs/ARCHITECTURE.md`
2. `app/main.py`
3. `app/bot/private_chat_runtime.py`
4. `app/services/`

### 想理解“现在正在做什么”

读：

1. `docs/NEXT_STEP.md`
2. `docs/STATUS.md`
3. `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`（需要看当前主线细节时）
4. `docs/TELEGRAM_BOT_SLIMMING_LOG.md`（需要看上一条主线闭环时）
5. `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`（需要看更早主线闭环时）
6. `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`（需要看更早主线闭环时）
7. `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`（需要看再更早主线闭环时）
8. `docs/PERSISTENCE_CLOSURE_LOG.md`（需要看更早完成主线闭环时）
9. `docs/CLEANUP_VERIFICATION_WINDOW.md`（需要看 cleanup 已完成证据时）

### 想理解“为什么不能随便改”

读：

1. `docs/DECISIONS.md`
2. `AGENTS.md`

### 想把项目跑起来

读：

1. `docs/GETTING_STARTED.md`
2. `docs/TEST_ENV.md`
3. `.env.example`
4. `Makefile`

## 4. 文档维护规则

- 同一条事实尽量只写一处；其他文档用“引用/跳转”，不要复制粘贴。
- `NEXT_STEP` 只写当前目标，`STATUS` 只写当前快照，当前主线的详细闭环优先收口到对应主线台账（当前为 `docs/IMPORT_TO_LIBRARY_SLIMMING_LOG.md`），不要把活动台账全文抄进去。
- **`STATUS.md` 和 `PERSISTENCE_CLOSURE_LOG.md` 不再逐天或逐字段追加 `截至 20xx-xx-xx 分流缺口` 条目**：新闭环优先合并进 `PERSISTENCE_CLOSURE_LOG.md` 的已有主题分组（2.1~2.5），`STATUS.md` 最多补一句当前结论或风险；commit 轨迹看 `git log`，不再重复粘贴。
- 运行方式、环境变量、启动入口一律收口到 `docs/GETTING_STARTED.md` 和 `.env.example`。
- 系统结构解释一律收口到 `docs/ARCHITECTURE.md`。
