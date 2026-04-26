# docs/OPERATOR_RUNBOOK.md (v5)

> 目的：给非技术操作者几条可直接复制给 AI 的短模板，不再长期维护一大段自由发挥提示词。

## 0. 怎么选模板

- 只想最快继续当前主线：先复制 `docs/STATUS.md` 末尾的 `Recommended Next Operator Command`
- 想继续当前主线：用“默认 3 轮施工”
- 想在同一会话里连续长跑，但不超过仓库约定上限：用“连续 10 轮施工（封顶版）”
- 不确定最近提交和文档有没有漂移：用“只做冷启动一致性检查”
- 这轮只想修文档入口和 docs gate：用“只做文档收口，不改业务代码”

如果你只记得一步：先看 `docs/STATUS.md`，再回这里复制一条模板。

## 1. 默认 3 轮施工

适用：你只知道“继续推进当前仓库”，希望 AI 按当前主线自己找最小闭环、自己验证、自己提交。

```text
按 AGENTS.md + docs/STATUS.md + docs/NEXT_STEP.md 执行。
如果 docs/NEXT_STEP.md 当前主线已完成，先做冷启动一致性检查；若无漂移，再从新的 operator 指定主线或当前结构债里选一个更小闭环。
如果 docs/NEXT_STEP.md 当前主线已完成，不要因为旧 Done when 已满足就立刻停止；应以当前选中的更小闭环作为本轮退出条件。
本机真实测试环境已就绪；凡是任务需要真实 downloader / import / refresh 验证，直接执行，不要留给我。
默认连续执行 3 轮；每轮只做一个最小闭环，自己验证、必要时更新文档、review diff、commit 并 push。
如果遇到 blocker、违反文档边界、无法确认 commit / push 状态，或已达到 docs/NEXT_STEP.md 的 Done when 任一条，就停止并简短汇报。
```

当前若只是“继续推进仓库”，优先仍先复制这一条；是否切线、切到哪条主线，以 `docs/NEXT_STEP.md` 当前真相为准。

## 2. 连续 10 轮施工（封顶版）

适用：你已经确认这次要让 AI 连续推进更久，但仍要求它遵守同一会话最多 10 轮的小步闭环纪律。

```text
按 AGENTS.md + docs/STATUS.md + docs/NEXT_STEP.md 执行。
如果 docs/NEXT_STEP.md 当前主线已完成，先做冷启动一致性检查；若无漂移，再从新的 operator 指定主线或当前结构债里选一个更小闭环。
如果 docs/NEXT_STEP.md 当前主线已完成，不要因为旧 Done when 已满足就立刻停止；应以当前选中的更小闭环作为本轮退出条件。
本机真实测试环境已就绪；凡是任务需要真实 downloader / import / refresh 验证，直接执行，不要留给我。
默认连续执行 10 轮；每轮只做一个最小闭环，自己验证、必要时更新文档、review diff、commit 并 push。
如果遇到 blocker、违反文档边界、无法确认 commit / push 状态、出现收益递减，或已达到 docs/NEXT_STEP.md 的 Done when 任一条，就停止并简短汇报。
```

只有当你明确知道自己要一口气推进更久时，再用这一条；否则默认还是优先用“默认 3 轮施工”。

## 3. 只做冷启动一致性检查

适用：你想先知道“文档、最近提交、当前状态”有没有漂移，不想它先动业务代码。

```text
按 AGENTS.md 执行。
先做冷启动一致性检查：读取 docs/INDEX.md、docs/ARCHITECTURE.md、docs/NEXT_STEP.md、docs/DECISIONS.md、docs/STATUS.md，运行 git log --oneline -20，并核对 STATUS 与 NEXT_STEP 是否一致。
如果发现漂移，这一轮只补文档，不改业务代码；否则再从当前主线里选一个最小闭环继续做。
```

## 4. 只做文档收口，不改业务代码

适用：你要它先修 README、STATUS、INDEX、runbook 这类入口层，不要碰 service / repo / bot 行为。

```text
按 AGENTS.md 执行。
这一轮只改文档与 docs gate，不改业务代码、不改协议、不改 SQLite 真相边界。
目标是让非技术操作者更容易继续推进：必要时更新 README、docs/INDEX.md、docs/STATUS.md、docs/NEXT_STEP.md、docs/HUMAN_START_HERE.md、docs/OPERATOR_RUNBOOK.md 和相关测试。
改完后自行运行针对性验证、review diff、commit 并 push。
```

## 5. 用完后看哪里

- 想知道 AI 做完没有：看 `docs/STATUS.md`
- 想知道当前唯一主线是什么：看 `docs/NEXT_STEP.md`
- 想知道最常用的验证 / 启动入口：看 `docs/GETTING_STARTED.md`
- 想知道它到底改了什么：看最新 commit 和相关台账
- 想判断下一轮该复制哪句：回到本页第 `0` 节
