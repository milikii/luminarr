# Cleanup verification window (2026-04-05 to 2026-04-12) (v12)

## Window

- 当前状态：进行中
- 开始日期：2026-04-05
- 最早可结束日期：2026-04-12
- 窗口活性：未到最早可结束日期
- 聚合 smoke gate：`tests/test_cleanup_cross_channel_smoke.py`
- 当前目标：四个渠道都至少完成 1 次真实私聊 cleanup smoke，确认“消息进来 -> shared runtime -> 文本回去”不回退。
- 当前结论：验证窗口仍在进行中；截至 2026-04-06，尚未到最早可结束日期 2026-04-12，四个渠道真实私聊 cleanup smoke 记录仍待补，暂未满足退出条件。

## Exit checklist

- [ ] 完成 2026-04-05 到 2026-04-12 的真实使用验证窗口
- [ ] Telegram 完成至少 1 次真实私聊 cleanup smoke
- [ ] personal WeChat 完成至少 1 次真实私聊 cleanup smoke
- [ ] Feishu 完成至少 1 次真实私聊 cleanup smoke
- [ ] WeCom 完成至少 1 次真实私聊 cleanup smoke
- [x] `tests/test_cleanup_cross_channel_smoke.py` 持续通过
- [x] cleanup discoverability / inspect / execution / rejection guidance / success follow-up / failure observability 没有协议回退

## Channel progress

| 渠道 | 状态 | 最近一次日期 | 备注 |
| --- | --- | --- | --- |
| Telegram | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |
| personal WeChat | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |
| Feishu | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |
| WeCom | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |

## Verification evidence

- 最近一次聚合 smoke gate：2026-04-06，`128 passed`（`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）
- 最近一次 cleanup 协议回归验证：2026-04-06，`223 passed, 91 deselected`（`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup`）
- 当前 cleanup 协议观察：截至 2026-04-06，cleanup discoverability / inspect / execution / rejection guidance / success follow-up / failure observability 未见协议回退；当前缺口只剩四渠道真实私聊 smoke 证据。

## Update rule

- 每次真实私聊 smoke 完成后，立刻把对应渠道状态改成 `已完成`，并写入绝对日期。
- 已完成渠道写入的真实私聊 smoke 日期不得早于窗口开始日期，也不得晚于当前结论快照日期；不要把窗口外日期回填成窗口内证据。
- 最早可结束日期之前，`窗口活性` 保持为 `未到最早可结束日期`；`当前结论` 也要显式写出“尚未到最早可结束日期 <绝对日期>”。
- 到达最早可结束日期但退出条件未满足时，`窗口活性` 改成 `已到最早可结束日期，待补退出条件`；`当前结论` 也要显式写出“已到最早可结束日期 <绝对日期>，但退出条件仍未满足”。
- 退出条件满足后，`当前状态` 改成 `已完成`，`窗口活性` 改成 `已满足退出条件`，`当前结论` 同步写成已满足退出条件。
- 即使四渠道真实私聊 smoke 和协议回归项都已补齐，也不得早于最早可结束日期把验证窗口标记为 `已完成`。
- 验证窗口仍在进行中时，`当前结论`、最近一次聚合 smoke gate 和 cleanup 协议回归验证日期必须同步到当天日期；只有窗口已完成后，才允许保留完成日快照。
- 每次重跑 `tests/test_cleanup_cross_channel_smoke.py` 或 focused cleanup 回归集后，立刻把最新日期、结果和命令同步写回这份台账，并同步勾选或取消 exit checklist 里的 smoke gate / cleanup 协议两项。
- 如果 smoke 暴露回归，只允许记录并修 shared runtime、渠道胶水或显式中文日志缺口，不新增 cleanup 行为。
- `docs/STATUS.md` 只保留当前窗口快照；这份文件负责保留当前窗口的逐项证据。
