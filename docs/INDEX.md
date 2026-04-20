# docs/INDEX.md (v11)

> 目的：先按你的身份分流，再决定读哪份文档；不要一上来翻完整个仓库文档表。

## 1. 如果你是操作者

先按这个顺序读：

1. `docs/HUMAN_START_HERE.md`
2. `docs/STATUS.md`
3. `docs/OPERATOR_RUNBOOK.md`
4. `docs/GETTING_STARTED.md`

你最常用的入口：

- `docs/HUMAN_START_HERE.md`：不会代码的人先看这里
- `docs/OPERATOR_RUNBOOK.md`：直接复制给 AI 的短模板
- `docs/GETTING_STARTED.md`：怎么启动、怎么做最小 smoke
- `docs/STATUS.md`：现在稳不稳、最近验证到哪

## 2. 如果你是 AI / 施工代理

先按这个顺序读：

1. `AGENTS.md`
2. `docs/NEXT_STEP.md`
3. `docs/STATUS.md`
4. `docs/DECISIONS.md`
5. `docs/ARCHITECTURE.md`

按需再读：

- `docs/PERSISTENCE_CLOSURE_LOG.md`：当前真相闭环细节
- `docs/TEST_ENV.md`：真实 downloader / import / refresh 联调
- 对应主线的 `*_LOG.md` / `*_PLAN.md`：只在当前任务直接相关时再打开

## 3. 如果你是开发者 / fork 维护者

先按这个顺序读：

1. `README.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DECISIONS.md`
4. `docs/STATUS.md`
5. `docs/NEXT_STEP.md`
6. `docs/GETTING_STARTED.md`

只有在你要接手旧主线或排旧债时，再去看：

- `docs/PERSISTENCE_CLOSURE_LOG.md`
- 当前相关的 `*_SLIMMING_LOG.md`
- 当前相关的 `*_PLAN.md`

## 4. 文档分层

- 操作者入口层：`README.md`、`docs/HUMAN_START_HERE.md`、`docs/OPERATOR_RUNBOOK.md`
- 运行与启动层：`docs/GETTING_STARTED.md`、`docs/TEST_ENV.md`
- 当前施工真相层：`docs/STATUS.md`、`docs/NEXT_STEP.md`
- 长期边界层：`docs/DECISIONS.md`、`docs/ARCHITECTURE.md`
- 历史闭环层：`docs/PERSISTENCE_CLOSURE_LOG.md`、各 `*_LOG.md` / `*_PLAN.md`

## 5. 文档维护规则

- `README.md` 只负责项目是什么、先看哪里、下一句怎么推进；不要再写当前主线长列表。
- `docs/HUMAN_START_HERE.md` 只服务非技术操作者；`AGENTS.md` 只服务 AI 执行。
- `docs/STATUS.md` 只保留当前短快照；不要把长台账再写回去。
- `docs/NEXT_STEP.md` 只写当前唯一主线、当前用户价值、边界和退出条件。
- 新闭环优先并入 `docs/PERSISTENCE_CLOSURE_LOG.md` 2.1~2.5 现有主题分组，不新开按日期堆叠的小节。
- 运行方式、环境变量、启动入口只写在 `docs/GETTING_STARTED.md` 和 `.env.example`。
- 系统结构解释只写在 `docs/ARCHITECTURE.md`。
