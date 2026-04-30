# T18 成人 BT 来源角色底座

**你在执行这个 task。开发者不会直接阅读这份文件。**

## 目标

把成人 BT 来源固定成一个可持续扩站的角色底座，避免后续每加一个站点就重写搜索、排序、说明文案或 helper 行为。

## 当前真相

- 当前唯一执行入口是 `docs/TASKS.md` 中第一个未完成项 `T18 成人 BT 来源角色底座`。
- `docs/NEXT_STEP.md` 已锁定本轮只做 `T18`，`T19` 不提前启动。
- `T16` 的 duplicate memory 语义和 `T17` 的 Telegram-first 高频交付层都已经完成，不能回退。

## 本轮必须满足

1. 为成人 BT 来源建立稳定的“角色”真相，至少能显式区分：
   - 主力 BT 来源
   - 辅助 PT 成人来源
   - helper-only 来源
2. `javlibrary` 必须继续锁定为 helper-only：
   - 可以继续用于只读补全或展示增强
   - 不能进入主动下载来源
   - 不能重新混进搜索结果主语义
3. 成人 BT 搜索、排序和说明文案应基于角色真相工作，而不是继续散落多个站点名判断。
4. 变更必须保持当前边界不回退：
   - adult-only BT 边界不变
   - 显式 `confirm` 边界不变
   - `watchlist sync` fail-closed 不变
   - `T16` duplicate warning / explicit continue 语义不变
   - `T17` Telegram-first 交付体验不变

## 建议实现方向

- 优先把来源角色真相收口到 `app/services/bt_sources.py`，让调用方消费角色数据，而不是继续复制站点常量。
- `app/main.py` 里 BT 来源装配应体现角色区分，避免 helper-only 来源被当成主动 provider 注入搜索主链。
- `app/services/bt_read_only_display.py` 的排序优先级、别名映射和 helper 行为如果需要调整，应围绕角色真相做最小收口。
- `app/services/search_media.py` 和相关 display path 只做必要适配，不顺手重构无关搜索链。

## 非目标

- 不提前启动 `T19` 聚合验证与运维真相同步。
- 不引入新的非成人 BT 主线、动漫 BT、`raw_bt subscription`、auto-confirm 或 `watchlist -> btsub` 桥接。
- 不把 Feishu / WeCom / personal WeChat 一起拖进这一轮。
- 不修改 `ExecutionGate` 或 non-Telegram 后台通知主线。
- 不扩成新的重量级证据账本或数据库 schema 改造，除非没有它就无法表达来源角色真相。

## 关键文件

- `app/services/bt_sources.py`
- `app/clients/web_source.py`
- `app/services/search_media.py`
- `app/services/bt_read_only_display.py`
- `app/main.py`

## 完成标准

- 来源角色真相稳定存在，后续扩站不需要重写搜索、排序和交付语义。
- `javlibrary` 继续只做 helper-only 补全，不会进入主动下载来源。
- 成人 BT 结果排序、说明文案和 helper-only 行为保持一致，不回退到零散站点脚本状态。
- focused tests 与主线回归继续通过。

## 必跑验证

- `make quality`
- `make verify-mainline`
- `make verify-adult-bt-wedge`
- `make lint`
