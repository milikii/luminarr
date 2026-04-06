# docs/INDEX.md (v1)

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
3. `docs/CLEANUP_VERIFICATION_WINDOW.md`

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
- `NEXT_STEP` 只写当前目标，`STATUS` 只写当前快照，不要把活动台账全文抄进去。
- 运行方式、环境变量、启动入口一律收口到 `docs/GETTING_STARTED.md` 和 `.env.example`。
- 系统结构解释一律收口到 `docs/ARCHITECTURE.md`。
