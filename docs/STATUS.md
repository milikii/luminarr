# Current status (v535)

## Current mainline
- **质量硬化** 已正式收工；当前唯一主线切到 **services 层数据结构降本**。
- 文档真相已对齐 D-039：后续优先收 services 层里稳定可复用的数据结构和解析逻辑，先从重复形状最明显、验证成本最低的地方下手。
- 本轮已把 watchlist 与 BT 订阅重复的 `movie/series/anime` alias、label 和前缀解析收口到 `app/services/media_kind.py`，保持两条路径原有默认行为不变。
- 本轮继续删除 BT 订阅侧单用途 `bt_subscription_media_kind_label()` 转发薄壳，扫描命中回复和列表格式化都直接复用 shared media kind helper。
- 当前继续保持不改协议、SQLite schema、调度语义或下载 / 导入 / 刷新真相边界。
- 当前质量 gate 仍保持可复验；后续每轮先做一个最小结构闭环，再补 focused tests 和文档同步。
- `cleanup_*_support.py` 当前为 `0` 个，继续保持完成态。
- `*_support.py` 当前只剩 4 个较大边界：`approval_repo_support.py`、`job_repo_support.py`、`bt_subscription_repo_support.py`、`subtitle_translation_support.py`；不按文件名机械强拆。

## Current health
- 默认分支质量 gate 仍是可复验的；最近一次通过结果保持 `27 passed, 0 skipped`。
- 当前没有新的业务回归信号；这次切线来自文档决策，不是红灯修复。
- 下一轮优先挑 services 层里稳定可复用的数据结构或解析逻辑，做最小抽离并补 focused tests。

## Latest verification
- `tests/test_media_kind.py tests/test_manage_bt_subscription.py` 通过（`42 passed`）。
- `tests/test_media_kind.py tests/test_manage_watchlist.py tests/test_manage_bt_subscription.py` 通过（`62 passed`）。
- 上一轮质量硬化 focused tests 与 `make quality` / `make verify-mainline` 都已通过，当前继续保持该已验证状态。

## Current biggest risk
- services 层里仍有重复的数据结构和解析 helper；切线后应先收最容易验证的共享部分，避免跨模块搬大块责任。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。

当前唯一主线是 services 层数据结构降本。优先从重复数据结构、解析 helper 或共享 label/alias 里挑一个最小闭环；不要重建已收掉的小 support 文件，不要切成人 BT 新功能，不改协议或 SQLite 真相边界。
```
