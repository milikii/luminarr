# Next step (v352)

## Current goal

- 当前主线已从 **成人 BT 专线基础收口** 切到 **成人 BT 专线质量复验**。
- 当前已保持完成态：
  - 成人 BT 站点优先、Prowlarr 成人 PT 补充
  - 成人内容 ID 识别与历史账本
  - BT 只读预览 / 批量预览里的历史提醒
  - 下载完成后的成人归档与统一保留期清理框架
- 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态：`app/bot/private_chat_runtime.py` 当前 `476` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退。
- 当前 direct magnet 入口 **继续保留** “观影 PT 链 / BT 成人链” 问询；shared runtime / Telegram wrapper 已对齐这条边界，不能自动假定所有磁力都走成人 BT。

## User value

- 成人资源站点现在不再只能依赖 Prowlarr 补全，`tokyotosho` / `sukebei(offkab)` / `javbus` 已进入 BT 来源模板。
- direct magnet 现在不只是文档要求，实际运行时也会先问“观影 PT 链 / BT 成人链”；当用户选择 `BT 成人链` 时，会直接创建成人磁力下载待确认，并尽量从 `dn=` 识别番号 / 分类。
- BT 预览和待确认现在会尽量识别内容 ID，并提示：
  - 已有待确认
  - 已在下载
  - 已归档保留
  - 已归档后清理
- 成人 BT 下载完成后，当前 sidecar 已能按内容分类归档，并在统一保留窗口后清理下载器任务与源资源；命中 `adult_content_registry` 的任务不会误回流普通 auto-import 主链。

## Only do

- 继续收口当前主线时，只做成人 BT 专线质量复验的小闭环：
  - direct magnet 问询边界与成人链待确认回归补稳
  - 成人归档 / 保留期清理 sidecar 的 focused / larger gate 补稳
  - 文档、运行时和测试对当前成人 BT 真相保持一致
- direct magnet 继续先问链路，不放宽成自动成人 BT。

## Do not do

- 不把 direct magnet 默认改成成人 BT 自动直投。
- 不把动漫 BT 再拉回主线；动漫继续走 PT 链。
- 不把这一步扩成浏览器自动化、登录态站点、CAPTCHA 或通用爬站平台。

## Done when

当前这条 **成人 BT 专线质量复验** 主线满足：

1. direct magnet runtime 与文档都使用“观影 PT 链 / BT 成人链”问询，不回退。
2. 用户选择 `BT 成人链` 时，可直接生成成人磁力下载待确认，并尽量识别番号 / 分类。
3. 成人下载完成任务命中 `adult_content_registry` 时，会优先走归档 sidecar；`archived_deleted` 终态不会误回流普通 auto-import 主链。
4. `make quality`、`make verify-mainline`、`make test` 都保持绿灯。

## After this step

1. 如果继续按质量方向推进，优先做成人归档 / 保留期清理的真实 smoke，确认 sidecar 在现有测试环境里不回归。
2. 如果继续沿成人 BT 方向推进，优先补 `javlibrary` helper 的只读识别补全，但不放宽成自动 dispatch 来源。
