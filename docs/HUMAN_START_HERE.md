# docs/HUMAN_START_HERE.md (v3)

> 目的：给**不会写代码**的人一个稳定入口，知道“先看哪里、下一句怎么发、结果去哪里看、失败先去哪里查”。

## 1. 这项目现在是什么

- 它是一个自托管影视自动化项目，不是聊天机器人平台
- 你发一句自然语言，它去做搜索、审批、下载、入库、刷新和状态查询
- 代码里现在有 Telegram / personal WeChat / Feishu / WeCom 四个私聊入口
- 但当前保守首版发布承诺只先冻结为：Telegram 私聊 + PT Transmission + Emby + movie-first 主链
- 当前最稳的是 movie-first 场景；更细的工程边界看 `docs/DECISIONS.md`

## 2. 你最常用的文档

1. `docs/HUMAN_START_HERE.md`
2. `docs/STATUS.md`
3. `docs/OPERATOR_RUNBOOK.md`
4. `docs/GETTING_STARTED.md`

如果你只记得一条原则：**不要先读历史台账，先看 `STATUS` 和 `RUNBOOK`。**

## 3. 你最常做的三件事

### 想继续让 AI 施工

直接复制：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```

如果你是要回头重开“发布口径 / 质量入口 / 真实 smoke”收口，再去 `docs/OPERATOR_RUNBOOK.md` 里复制“收尾发布准备”模板。

### 想知道项目现在稳不稳

去看 `docs/STATUS.md`：

- `Current health`：看现在是绿灯、黄灯还是红灯
- `Latest verification`：看最近一次真实验证和 focused 验证
- `Current biggest risk`：看当前最容易翻车的地方

### 想启动或重启项目

直接去 `docs/GETTING_STARTED.md`，不要先翻 `AGENTS.md`。

## 4. 看结果去哪里

- 当前主线和下一步：`docs/NEXT_STEP.md`
- 当前状态：`docs/STATUS.md`
- 历史详细闭环：`docs/PERSISTENCE_CLOSURE_LOG.md`
- 启动、环境、测试栈：`docs/GETTING_STARTED.md`、`docs/TEST_ENV.md`

## 5. 失败先看哪里

- 启动失败：`docs/GETTING_STARTED.md`
- 当前主线为什么没继续：`docs/STATUS.md` + `docs/NEXT_STEP.md`
- 真实 downloader / import / refresh 环境：`docs/TEST_ENV.md`
- AI 为什么不该那样改：`AGENTS.md`

## 6. 给 fork 维护者的最短入口

如果以后换别人接手，先读：

1. `docs/ARCHITECTURE.md`
2. `docs/DECISIONS.md`
3. `docs/STATUS.md`
4. `docs/NEXT_STEP.md`
5. `AGENTS.md`

高风险边界不要从代码里猜，直接看 `AGENTS.md` §12 和 `docs/DECISIONS.md`。
