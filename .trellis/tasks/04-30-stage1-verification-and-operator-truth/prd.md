# T19 Stage 1 聚合验证与运维真相同步

**你在执行这个 task。开发者不会直接阅读这份文件。**

## 目标

在 `T16`、`T17`、`T18` 已完成的前提下，补一轮 Stage 1 focused verification 和 operator-facing 文档同步，确保新的 Stage 1 主线不只是开发者上下文里的真相。

## 当前真相

- `T16 成人 BT 下载前防重记忆层`、`T17 Telegram-first 高频主链交付层`、`T18 成人 BT 来源角色底座` 都已完成并已提交。
- `docs/NEXT_STEP.md` 已把当前唯一执行入口切到 `T19 Stage 1 聚合验证与运维真相同步`。
- 当前不再做新功能，只做验证、证据和文档真相同步。

## 本轮必须满足

1. 建立可重复运行的 Stage 1 focused verification 入口，覆盖：
   - duplicate memory
   - Telegram-first 高频链
   - 成人 BT 来源角色底座
2. 同步 operator-facing 文档，使其与当前实现一致：
   - `docs/STATUS.md`
   - `docs/NEXT_STEP.md`
   - `docs/GETTING_STARTED.md`
   - 必要时 `docs/OPERATOR_RUNBOOK.md`
3. 补至少一轮新的 Telegram 实机 smoke 或等价证据。
4. 以下 gate 继续通过：
   - `make quality`
   - `make verify-mainline`
   - `make verify-adult-bt-wedge`
   - `make lint`

## 非目标

- 不开启新的功能主线。
- 不回切影视 BT、动漫 BT、`raw_bt subscription`、auto-confirm 或新的 `watchlist -> btsub` 桥接。
- 不顺手改 `ExecutionGate`、non-Telegram 后台通知主线或 duplicate memory 的账本边界。
- 不把运行依赖真相重新分散回多个文档入口。

## 关键文件

- `Makefile`
- `tests/`
- `docs/STATUS.md`
- `docs/NEXT_STEP.md`
- `docs/GETTING_STARTED.md`
- `docs/OPERATOR_RUNBOOK.md`

## 完成标准

- Stage 1 focused verification 入口可重复运行，且覆盖 `T16` / `T17` / `T18` 三条子线。
- 文档与当前实现一致，不再保留冻结态或 `T17` 口径。
- Telegram 实机 smoke 或等价证据已补充。
- 四个主 gate 全绿。
