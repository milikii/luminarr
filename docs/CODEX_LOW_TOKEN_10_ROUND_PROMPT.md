# Codex low-token 10-round prompt

> 用途：给 Codex 的连续推进提示词模板。
> 目标：保持“10 轮、每轮一个最小闭环”的推进节奏，同时减少不必要的全文重读和 token 消耗。

## Prompt

```text
按仓库根目录 `AGENTS.md` 执行。

你可以自行召唤子代理提升效率，但每轮仍只允许完成一个最小闭环任务，并由你统一汇总结果。
本机真实测试环境已就绪；Transmission / Emby 测试容器已启动，凡是任务需要真实 downloader / import / refresh 验证，直接执行，不要留给我。

本次会话默认连续执行 10 轮。除非出现以下任一情况，否则必须继续下一轮：
1. 明确 blocker
2. 明确达到 `docs/NEXT_STEP.md` 当前主线退出条件
3. 继续修改会违反 `AGENTS.md` 或当前文档边界
4. 无法确认 commit / push 状态

第 1 轮先做冷启动一致性检查：
1. 读取 `AGENTS.md`、`docs/INDEX.md`、`docs/ARCHITECTURE.md`、`docs/NEXT_STEP.md`、`docs/DECISIONS.md`、`docs/STATUS.md`
2. 运行 `git log --oneline -20`
3. 对比 `docs/STATUS.md`
4. 如果发现文档漂移，第 1 轮只补文档，不改业务代码

第 2-10 轮不要机械重读全文。默认只读：
1. `AGENTS.md`
2. `docs/NEXT_STEP.md` 当前主线相关段落
3. `docs/STATUS.md` 当前快照
4. 与本轮任务直接相关的代码、测试、最近 `git log --oneline -5`
5. 只有在需要看当前主线详细历史时，才按需读取 `docs/PERSISTENCE_CLOSURE_LOG.md`
6. 只有在需要核对 cleanup 已完成证据时，才按需读取 `docs/CLEANUP_VERIFICATION_WINDOW.md`

如果某一轮结束后没有立刻看到下一步：
1. 不允许直接停止
2. 先重新扫描 `docs/NEXT_STEP.md` 相关段落、`docs/STATUS.md` 当前快照、相关代码和最近 5 个提交
3. 从当前主线里再选一个更小、更保守的收口任务继续做
4. 只有在完成这次重新扫描后，仍然满足停止条件，才允许停止

每轮流程固定为：
1. 只选一个最小闭环任务
2. 直接实施并自行验证
3. 必要时更新相关文档
4. review diff，确认没有 scope creep
5. commit 并 push
6. 立即开始下一轮，不要停下来等我确认

文档写作要求：
1. 不要把长台账再写回 `docs/STATUS.md`
2. `docs/STATUS.md` 只保留当前快照
3. 当前主线的详细闭环、focused tests、commit 轨迹优先写入 `docs/PERSISTENCE_CLOSURE_LOG.md`
4. cleanup 已完成窗口的详细证据只写入 `docs/CLEANUP_VERIFICATION_WINDOW.md`
5. 不要在汇报里大段复述文档原文，只用 1-2 句中文概括当前真相

默认对我只做简短汇报，每轮只输出这些内容：
- 第几轮
- 本轮任务
- 是否验证通过
- 改了哪些文件
- 是否更新文档
- commit hash
- 下一轮要做什么

只有在失败、遇到 blocker、或必须由我决定时，才展开说明细节。
```

## Recommended use

- 新开会话时直接把上面的 `Prompt` 整段贴给 Codex。
- 如果当前任务和 cleanup 已完成窗口无关，不要额外要求它重读 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
- 如果只想跑 3-5 轮，把首段里的“默认连续执行 10 轮”改成对应轮数即可。
