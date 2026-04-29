# BLOCKERS.md

## 2026-04-29 — non-Telegram 一等公民主线缺少最小运行画像

- 当前阻断任务：`docs/TASKS.md` 第 6 个未完成项“把 non-Telegram 运行模式做成一等公民”
- 阻断原因：
  - 当前代码已完成 `telegram_sidecar_runtime.py` 宿主解耦，但“成为一等公民”不再是单一宿主问题
  - 该任务会同时触碰：
    - 运行入口
    - 部署与装机真相
    - 通知发送回路
    - operator 文档口径
  - 目前文档只给了方向，没有锁定“哪一个 non-Telegram 画像先成为一等公民、最小可交付边界是什么、哪些能力必须同轮具备”
- 已完成的前置工作：
  - `app/config.py` 启动硬依赖解耦（方案 A）已完成
  - `telegram_sidecar_runtime.py` 宿主解耦已完成
  - `manage_bt_subscription.py` 首个超大业务文件收口切口已完成
  - Feishu 依赖真相与 warning 隔离已完成
- 建议下一步：
  - 先锁一个最小画像，例如：
    - `Feishu-only text private chat can boot and receive/reply`
    - 或 `WeCom-only webhook + shared runtime can boot independently`
  - 把“必须具备的能力 / 可以继续缺失的能力 / focused tests”写成单轮边界后再继续
