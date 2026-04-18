# docs/SLIMMING_RULES.md (v1)

> 目的：把"编排层瘦身 / 模块化"这类主线的共用纪律固化，让 Codex 不用每次重新拍板。
>
> 适用范围：`docs/NEXT_STEP.md` 里所有 `XXX.py 瘦身 / 模块化` 主线（`telegram_bot.py` / `import_to_library.py` / `add_to_downloader.py` / `search_media.py` / `manage_bt_subscription.py` / `cleanup_downloaded_source.py` / `private_chat_runtime.py` / `app/main.py`），以及将来任何以"拆大文件、不改行为"为目标的主线。

## 1. 什么算"瘦身"

- **只**拆代码组织，不改对外行为、不改真相边界、不改副作用。
- 允许：抽函数到新模块、把类里相对独立的一组方法搬到新文件、提出共享常量。
- 不允许：改 approval / jobs / job_event / SQLite schema / 审批协议 / 用户侧文本 / 中文日志文本 / error reason 字符串。
- 任何会让调用方感知到的 API 变化都视为**另一个主线**，不走瘦身 PR。

## 2. 拆分粒度

- **每个 commit 只拆出一个 helper 模块或一组同属职责的方法。** 不要一次把一个大文件拆成 5 个模块。
- 单次瘦身 commit 的代码改动（含新增、删除、移动行）目标控制在 **< 400 行 diff**。超过就拆成两个 commit。
- 新文件放在原文件所在目录（`app/services/` 或 `app/bot/`），命名遵循现有风格（小写+下划线）。
- 不要引入新的子包层级（如 `app/services/download/...`），除非单个主线拆完明显分簇后，用户显式同意引入。

## 3. 命名约定

- 抽出的 helper 文件以"职责 + `_helper.py`"或职责名本身命名：
  - `add_pending_context.py`（当前）✓
  - `import_naming_truth.py`（假想）✓
  - `download_dispatcher_helper.py`（假想）✓
- 抽出的模块内**不**再建同名大类；优先用独立函数或 `@dataclass(frozen=True, slots=True)`。
- 共享常量（错误 reason 字符串、中文文案）抽到对应 helper 文件顶部；不要新建 `constants.py` 聚合。

## 4. pyflakes / import 清理（硬性要求）

- **每个瘦身 commit 必须顺手清掉对应被拆文件里的 pyflakes 未用 import**（尤其是 `imported but unused`）。
- 这一条不单独开 commit、不单独开主线；直接合进瘦身本身。
- 验证命令：
  ```bash
  .venv/bin/python -m pyflakes app/services/XXX.py app/bot/XXX.py
  ```
  目标：瘦身 commit 完成后，被动过的文件的 pyflakes 警告 **严格不增加**；能顺手清的就清。

## 5. 测试联动

- 瘦身前先跑一次对应 focused tests，确认当前 baseline 绿。
- 瘦身后**必须再跑一次同一套 focused tests**，结果必须一致（数量、通过状态）。
- 如果测试数量因为 helper 被暴露而新增了 unit test，允许增加；但原有测试的断言不能改、不能删。
- focused tests 入口继续写进对应 `docs/XXX_SLIMMING_LOG.md`。

## 6. 可测量退出条件

每个瘦身主线的 `Done when` 至少要满足：
1. 主文件行数下降到目标阈值（建议：< 800 行，除非主文件天生职责重；若超过说明分组不对）。
2. 对应 focused tests 仍全绿。
3. pyflakes 未用 import **严格不增加**。
4. 没有新增任何对外 API / 协议 / 真相边界变化。

## 7. 禁止项

- 禁止把瘦身扩成"顺手改签名""顺手优化算法""顺手改日志文本"。
- 禁止拆到"每个函数一个文件"的过度细分。
- 禁止引入新的框架、装饰器、继承关系；除非当前主线的 `After this step` 明确列了新抽象主线。
- 禁止顺手改 `tests/` 里的断言文案；如果瘦身后测试找不到常量，补 `__all__` / re-export，不要改测试。

## 8. 主线切换

- 瘦身主线完成后按 `docs/NEXT_STEP.md` `After this step` 顺序切下一条。
- 切换时在新主线对应的 `docs/XXX_SLIMMING_LOG.md` 里记最小起点（目标文件、当前行数、拆分方向指针到本文件 §2-§3）。
