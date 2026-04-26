# Next step (v354)

## Current goal

- 当前主线已从 **成人 BT 专线第二条真实 smoke 收口** 切到 **`javlibrary` helper 只读识别补全**。
- 当前完成态保持：
  - 成人 BT 站点优先、Prowlarr 成人 PT 补充
  - 成人内容 ID 识别与历史账本
  - BT 只读预览 / 批量预览里的历史提醒
  - 下载完成后的成人归档与统一保留期清理框架
  - qB 成人归档真实 smoke 通过
  - BT Transmission 成人归档真实 smoke 通过
- 当前新增真相：
  - `DOWNLOADER_INSTANCES` 当前可选第 5 段 `dispatch_download_dir`，可把下载器 API 投递路径和宿主机导入路径分开
  - 路由层当前会在导入查询时优先恢复任务真相里的 host `download_dir`
  - `tmp_tests/verify_adult_archive_bt_real_smoke.py` 当前会先清理同 hash 旧任务，再用 `/downloads/complete` 投递，已稳定跑通“归档 -> 保留期清理”
- 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态：`app/bot/private_chat_runtime.py` 当前 `476` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退。
- 当前下一条缺口：
  - `javlibrary` helper 还缺 BT-only read-only 识别补全
  - 当前成人标题识别仍主要依赖站点标题、`javbus` 与已有规则，不够覆盖 `javlibrary` 这条只读补充来源

## User value

- 成人资源站点、direct magnet 成人链待确认、历史账本和归档 sidecar 当前都不再停留在“理论上可行”。
- 当前两条真实下载器证据都已拿到：
  - qB 成人归档成功，保留期清理成功
  - BT Transmission 成人归档成功，保留期清理成功
- 下一步补 `javlibrary` helper 只读识别补全，可以在不放宽自动 dispatch 边界的前提下，继续提升成人 BT 标题识别稳定性。

## Only do

- 继续沿当前主线时，只做 `javlibrary` helper 的 BT-only read-only 小闭环：
  - 只补识别、归一化、只读补全
  - 只服务成人 BT 支线，不进 PT 主链
  - 只用于人工探索 / 只读识别补充，不直接写 approval / jobs / downloader dispatch 真相
  - 保持当前 qB / BT Transmission 真实 smoke 结果、测试环境与文档一致
- direct magnet 继续先问链路，不放宽成自动成人 BT。

## Do not do

- 不把 direct magnet 默认改成成人 BT 自动直投。
- 不把 `javlibrary` helper 放宽成自动 dispatch、自动确认或通用爬站平台。
- 不把动漫 BT 再拉回主线；动漫继续走 PT 链。
- 不把这一步扩成浏览器自动化、登录态站点、CAPTCHA 或通用爬站平台。

## Done when

当前这条 **`javlibrary` helper 只读识别补全** 主线满足：

1. `javlibrary` 只读 helper 能稳定补出当前成人 BT 识别所需的最小字段。
2. 补全结果只进入 BT-only read-only 识别路径，不写审批真相，不触发下载器副作用。
3. 现有 qB / BT Transmission 成人归档真实 smoke 不回退。
4. `make quality`、focused tests 和相关文档都已同步。

## After this step

1. 如果 `javlibrary` helper 只读识别补全也收口，再看是否需要补更窄的成人标题归一化回归保护。
2. 如果 `javlibrary` 识别补全仍有歧义，优先加 focused tests 和只读证据，不要先扩成自动 dispatch。
