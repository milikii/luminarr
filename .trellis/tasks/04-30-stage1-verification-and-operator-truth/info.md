# T19 实施上下文

## 任务性质

- 这是一个“验证 + 文档真相同步”任务，不是功能扩展任务。
- 允许改 `Makefile`、tests、operator-facing docs，以及必要的证据记录。
- 除非验证暴露真实缺陷，否则不要再改业务代码。

## 当前主线边界

- duplicate memory、Telegram-first 高频交付、adult BT source roles 已经完成。
- `docs/NEXT_STEP.md` 已经把 T19 定义为 Stage 1 收尾前的最后执行任务。
- 若验证暴露实现与文档不一致，优先修文档或补 focused verification；仅在必须时回修代码。

## 风险提醒

- 不要把 `STATUS.md` 再写回“冻结态”或旧的 `T17` 口径。
- 不要把 operator 真相扩散到多个并列入口；继续保持单一真相入口。
- 若要补实机 smoke 证据，尽量复用现有日志 / trace / operator 路径，而不是新造流程。
