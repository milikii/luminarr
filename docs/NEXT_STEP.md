# Next step (v352)

## Current goal

- 当前主线已切到 **成人 BT 专线基础收口**。
- 已落地范围：
  - 成人 BT 站点优先、Prowlarr 成人 PT 补充
  - 成人内容 ID 识别与历史账本
  - BT 只读预览 / 批量预览里的历史提醒
  - 下载完成后的成人归档与统一保留期清理框架
- 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态：`app/bot/private_chat_runtime.py` 当前 `467` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退。
- 当前 direct magnet 入口 **继续保留** “观影 PT 链 / BT 成人链” 问询；不能自动假定所有磁力都走成人 BT。

## User value

- 成人资源站点现在不再只能依赖 Prowlarr 补全，`tokyotosho` / `sukebei(offkab)` / `javbus` 已进入 BT 来源模板。
- BT 预览和待确认现在会尽量识别内容 ID，并提示：
  - 已有待确认
  - 已在下载
  - 已归档保留
  - 已归档后清理
- 成人 BT 下载完成后，当前 sidecar 已能按内容分类归档，并在统一保留窗口后清理下载器任务与源资源。

## Only do

- 继续收口当前主线时，只做成人 BT 专线的小闭环：
  - 成人站点规则补稳
  - 成人归档 / 保留期清理 focused tests 补齐
  - 历史账本与 direct magnet 问询边界补稳
- direct magnet 继续先问链路，不放宽成自动成人 BT。

## Do not do

- 不把 direct magnet 默认改成成人 BT 自动直投。
- 不把动漫 BT 再拉回主线；动漫继续走 PT 链。
- 不把这一步扩成浏览器自动化、登录态站点、CAPTCHA 或通用爬站平台。

## Done when

当前这条 **成人 BT 专线基础收口** 主线满足：

1. 成人 BT 网站优先、Prowlarr 成人 PT 补充的来源顺序已落地。
2. 成人内容 ID 与历史账本已进入 BT 预览、待确认和确认执行。
3. 成人下载完成后可进入归档，并在统一保留窗口后清理下载器任务与源资源。
4. direct magnet 入口仍保留“观影 PT 链 / BT 成人链”问询，不回退。

## After this step

1. 如果继续沿成人 BT 方向推进，优先补 `javlibrary` helper 的只读识别补全。
2. 如果继续按质量方向推进，优先跑更大的 focused / quality gate，确认成人归档 sidecar 不回归现有导入主链。
