# T18 实施上下文

## 来自仓库文档的边界

- `docs/NEXT_STEP.md`：当前只做 `T18`，不要提前碰 `T19`。
- `docs/TASKS.md`：`T18` 关键触点是 `bt_sources.py`、`web_source.py`、`search_media.py`、`bt_read_only_display.py`、`main.py`。
- `docs/STATUS.md` 仍停在 `T17` 口径，说明这轮实现完成前不要去更新状态页。

## 当前代码基线

- `app/main.py` 直接把 `settings.bt_web_sources` 里的每个站点装配成 `BtSourceProvider`，随后再附加可选 `prowlarr`。
- `app/clients/web_source.py` 当前把 `javlibrary`、`javbus`、`sukebei`、`tokyotosho` 等规则都放在同一层 `SUPPORTED_WEB_SOURCE_RULES` 里。
- `app/services/bt_sources.py` 目前只有 provider 合并、规范化和去重能力，还没有来源角色模型。
- `app/services/bt_read_only_display.py` 里存在成人来源排序优先级和来源别名映射；这是潜在的角色散落点。
- `app/services/search_media.py` 的 BT 只读展示链会经过 `BtReadOnlyDisplayService`，因此角色语义要在这里保持一致。

## 实施偏好

- 选择最小切口，把“来源角色”做成单点真相，而不是在多个文件复制 `if source == ...`。
- 可以调整当前站点配置解释方式，但不要把已有 operator 配置面扩大成新系统。
- 如果必须新增常量或数据结构，优先让现有调用方读取它，而不是再造一套并行 helper。

## 复验提醒

- 先做 focused tests，再跑：
  - `make quality`
  - `make verify-mainline`
  - `make verify-adult-bt-wedge`
  - `make lint`
