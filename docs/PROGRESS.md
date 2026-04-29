## Round 0 — 2026-04-28 00:00

### 完成
- 项目初始化

### 测试状态
- 通过: 0 / 总计: 0

### 遗留 / 下轮继续
- 等待按执行计划进入成人 BT minimum wedge

### 下轮目标
- 修复 docs gate 并开始 Task 1

## Round 1 — 2026-04-28 19:56

### 完成
- 补齐 `docs/PROGRESS.md`、`docs/BLOCKERS.md` 和 `.worktrees/` 忽略规则，解除执行前置阻断
- 归档 `docs/DEPLOY_CHECKLIST.md` 与 `docs/BT_SCORING_RULES.md`
- 调整 docs gate，将 `PROGRESS.md` / `BLOCKERS.md` 排除出 active docs 预算，并更新 `docs/GETTING_STARTED.md`

### 测试状态
- 通过: 35 / 总计: 35

### 遗留 / 下轮继续
- 继续执行成人 BT minimum wedge Task 2

### 下轮目标
- 增加 `成人搜` 只读查询别名并补齐成人只读回复详情链接

## Round 2 — 2026-04-28 20:01

### 完成
- 为 BT 只读查询增加 `成人搜` 显式入口别名
- 在成人只读探索和批量预览回复中展示 javlibrary 详情链接
- 更新只读说明文案，明确成人下载链应通过发送磁力并选择 `BT 成人链`

### 测试状态
- 通过: 18 / 总计: 18

### 遗留 / 下轮继续
- 继续执行成人 BT minimum wedge Task 3

### 下轮目标
- 让成人历史信息进入待下载回复

## Round 3 — 2026-04-28 20:08

### 完成
- 为 `AddPendingContextBuilder` 增加基于 `adult_content_registry` 的成人历史回填
- 让 direct magnet 待下载回复沿用成人历史文案
- 对不支持历史查询的轻量假 repo 保持 fail-open，不影响待下载创建

### 测试状态
- 通过: 10 / 总计: 10

### 遗留 / 下轮继续
- 继续执行成人 BT minimum wedge Task 4

### 下轮目标
- 增加成人 BT focused 验证入口并跑总 gate

## Round 4 — 2026-04-28 20:14

### 完成
- 新增 `make verify-adult-bt-wedge` 与对应 Makefile 测试
- 在 `docs/GETTING_STARTED.md` 增加成人 BT focused 验证入口
- 修复 `handle_confirm_query()` 对 confirm job lookup `RuntimeError` 未 fail-closed 的回归，确保新 focused target 通过
- 通过 `make verify-adult-bt-wedge`、`make quality`、`make verify-mainline`

### 测试状态
- 通过: 3 / 总计: 3

### 遗留 / 下轮继续
- 无

### 下轮目标
- 等待用户指令

## Round 5 — 2026-04-28 20:49

### 完成
- 启动本地 `app.main`，开启 Telegram 人工 smoke 前置运行环境
- 将 `AGENTS.md`、`STATUS.md`、`NEXT_STEP.md`、`TASKS.md` 切到 “adult BT 已完成 / 下一条主线为 config 启动硬依赖解耦” 的当前真相
- 同步执行计划尾部的最终验证状态与 active docs 预算统计口径

### 测试状态
- 待本轮文档收口后重跑 docs / quality gate

### 遗留 / 下轮继续
- 等待 Telegram 人工 smoke 结果

### 下轮目标
- 开始 `app/config.py` 启动硬依赖解耦

## Round 6 — 2026-04-29 00:44

### 完成
- 定稿 `docs/plans/2026-04-29-config-startup-dependency-decoupling.md`
- 锁定 config 主线方案 A：本轮只解耦 `PROWLARR_*` 与 legacy `TRANSMISSION_BASE_URL`；`TELEGRAM_BOT_TOKEN` 继续保持当前宿主必填
- 同步更新 `docs/STATUS.md`、`docs/NEXT_STEP.md`、`docs/TASKS.md`，让当前主线真相与计划一致

### 测试状态
- 通过: 3 / 总计: 3

### 遗留 / 下轮继续
- 按定稿计划进入 `app/config.py` capability contract 实施

### 下轮目标
- 先补 capability matrix 和 focused tests，再收口 config 校验与启动装配

## Round 7 — 2026-04-29 01:38

### 完成
- 完成 `app/config.py` 启动硬依赖解耦方案 A：`PROWLARR_*` 改为能力必填，legacy `TRANSMISSION_BASE_URL` 改为在已有可用 downloader instances 时可选
- 同步收口 `app/main.py` 装配、搜索 / `btsub run` unavailable guard、legacy downloader fallback fail-closed 语义
- 补齐 focused tests、`.env.example` 与 `docs/GETTING_STARTED.md` 能力边界说明
- 通过 reviewer 反馈闭环，确认 `bt搜` / `bt批量` 不被误伤，`btsub list/add/remove/clear` 在降级标记存在时仍可用

### 测试状态
- 通过: 3 / 总计: 3

### 遗留 / 下轮继续
- 进入 `telegram_sidecar_runtime.py` 宿主解耦主线

### 下轮目标
- 先盘点 Telegram `Application` 生命周期下当前承载的 sidecar 与 scheduler，再拆出非 Telegram 运行所需的宿主边界

## Round 8 — 2026-04-29 01:56

### 完成
- 完成 `telegram_sidecar_runtime.py` 宿主解耦：抽出通用 sidecar host 边界，Telegram 生命周期只保留 wrapper/委托
- 让 Feishu、WeCom、personal WeChat、下载完成轮询、post-download auto-import 与 `btsub` scheduler 通过通用 host 生命周期启动/停止
- 让 `btsub` scheduler 通知发送改走宿主注入的 `send_text` callback，而不是硬绑 `Application.bot.send_message`
- 补齐 sidecar focused tests，并通过总回归

### 测试状态
- 通过: 3 / 总计: 3

### 遗留 / 下轮继续
- 进入超大业务文件收口主线

### 下轮目标
- 先盘点 `add_to_downloader.py`、`import_to_library.py`、`manage_bt_subscription.py`、`search_media.py`、`cleanup_downloaded_source.py`、`subtitle_translation_support.py` 的体量与单消费者切口，再决定最小拆分顺序

## Round 9 — 2026-04-29 08:35

### 完成
- 将 `manage_bt_subscription.py` 的候选选择 / 打分解析 helper 下沉到 `bt_subscription_candidate_helpers.py`
- 新增 `bt_candidate_metadata.py` 作为公开 BT candidate metadata 解析边界，并让 `pure_bt` 与 `manage_bt_subscription` 复用同一套实现
- 为首个超大业务文件收口切口补齐 focused tests，并通过 spec/quality 两层复审

### 测试状态
- 通过: 3 / 总计: 3

### 遗留 / 下轮继续
- 进入 Feishu 可选依赖策略主线

### 下轮目标
- 盘点 `lark_oapi` 的真实运行边界和安装入口，收口 requirements / extras / operator docs 其中一个最小方案
