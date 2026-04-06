# Cleanup verification window (v4)

## Window

- 当前状态：进行中
- 开始日期：2026-04-05
- 最早可结束日期：2026-04-12
- 窗口活性：未到最早可结束日期
- 聚合 smoke gate：`tests/test_cleanup_cross_channel_smoke.py`
- 当前目标：四个渠道都至少完成 1 次真实私聊 cleanup smoke，确认“消息进来 -> shared runtime -> 文本回去”不回退。
- 当前结论：验证窗口仍在进行中；截至 2026-04-06，四个渠道真实私聊 cleanup smoke 记录仍待补，暂未满足退出条件。

## Exit checklist

- [ ] 完成 2026-04-05 到 2026-04-12 的真实使用验证窗口
- [ ] Telegram 完成至少 1 次真实私聊 cleanup smoke
- [ ] personal WeChat 完成至少 1 次真实私聊 cleanup smoke
- [ ] Feishu 完成至少 1 次真实私聊 cleanup smoke
- [ ] WeCom 完成至少 1 次真实私聊 cleanup smoke
- [ ] `tests/test_cleanup_cross_channel_smoke.py` 持续通过
- [ ] cleanup discoverability / inspect / execution / rejection guidance / success follow-up / failure observability 没有协议回退

## Channel progress

| 渠道 | 状态 | 最近一次日期 | 备注 |
| --- | --- | --- | --- |
| Telegram | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |
| personal WeChat | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |
| Feishu | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |
| WeCom | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |

## Update rule

- 每次真实私聊 smoke 完成后，立刻把对应渠道状态改成 `已完成`，并写入绝对日期。
- 最早可结束日期之前，`窗口活性` 保持为 `未到最早可结束日期`；到达最早可结束日期但退出条件未满足时，改成 `已到最早可结束日期，待补退出条件`。
- 退出条件满足后，`当前状态` 改成 `已完成`，`窗口活性` 改成 `已满足退出条件`，`当前结论` 同步写成已满足退出条件。
- 如果 smoke 暴露回归，只允许记录并修 shared runtime、渠道胶水或显式中文日志缺口，不新增 cleanup 行为。
- `docs/STATUS.md` 只保留当前窗口快照；这份文件负责保留当前窗口的逐项证据。
