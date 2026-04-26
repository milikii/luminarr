# docs/VERIFICATION_ENTRYPOINTS_PLAN.md (v1)

> 目的：把下一线程的主线固定为“验证入口收口 + 操作文档瘦身”，先降低维护成本和提示词噪声，再回到业务热点文件。

## 1. 真实问题

- `Makefile` 当前 `verify-mainline` 和 cleanup 入口过碎：
  - `verify-mainline` 现在是一长串按 `-k` 拼出来的 public command。
  - cleanup 公开 target 也比当前操作者真正需要的更多。
- `docs/OPERATOR_RUNBOOK.md` 仍带旧主线残留和重复说明；文档入口开始比代码主线更难读。
- 但当前项目的 approval / lease / version / confirm / recovery 真相边界仍是必要约束；这条主线不能为了“看起来简单”去删安全协议。

## 2. 当前主线只做什么

### 2.1 Makefile 公开入口收口

- 只收 `Makefile` 的**公开 target 形状**，不改业务测试语义。
- 下一线程固定目标：
  - `verify-mainline` 从碎片命令表收成少数几个分组 target 再汇总执行。
  - cleanup 的公开入口只保留操作者真正需要的少数几个：
    - `test-cleanup-smoke`
    - `test-cleanup`
    - `test-cleanup-docs-gate`
    - `test-cleanup-window`
- 可以继续保留 `-k` 作为第一轮过渡手段；这一步**不要求**同步引入 pytest marker 重写。

### 2.2 操作文档入口瘦身

- 只收这些入口文档：
  - `docs/OPERATOR_RUNBOOK.md`
  - `docs/STATUS.md`
  - `docs/NEXT_STEP.md`
  - 按需补 `docs/INDEX.md`
- 目标是：
  - 删除过时主线引用
  - 保留当前唯一默认推进路径
  - 让非技术操作者能用一条默认命令继续推进

## 3. 明确不做

- 不把 `verify-mainline` 直接粗暴改成单条 `pytest tests/ -q`。
- 不在这一轮删除 approval / lease / version / confirm / recovery 协议。
- 不在这一轮扩功能、改交互、改下载器/导入/归档链路。
- 不在这一轮顺手重写 `.env.example` 或大改 `AGENTS.md`；这些可作为后续文档/配置主线另开。

## 4. Done when

1. `Makefile` 的公开验证入口明显收口，`verify-mainline` 和 cleanup target 不再是操作者层面的碎片命令堆。
2. `docs/OPERATOR_RUNBOOK.md` 不再引用旧主线或过时 plan，默认模板只服务当前主线。
3. `docs/STATUS.md`、`docs/NEXT_STEP.md`、`docs/OPERATOR_RUNBOOK.md` 对“下一线程该做什么”表述一致。
4. `tests/test_cleanup_docs_consistency.py` 和这轮涉及的 Makefile / docs gate 均通过。

## 5. After this step

- 如果验证入口和文档入口都收口，再切回代码热点，优先看 `add_to_downloader.py`。
- 若后续仍要继续压文档/配置负担，再单开一条“`.env.example` / `AGENTS.md` 入口瘦身”主线，不和 Makefile 收口混做。
