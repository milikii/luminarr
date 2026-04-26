# Next step (v352)

## Current goal

- 当前主线已从 **成人 BT 专线质量复验** 切到 **成人 BT 专线真实 smoke blocker 收口**。
- 当前代码侧已保持完成态：
  - 成人 BT 站点优先、Prowlarr 成人 PT 补充
  - 成人内容 ID 识别与历史账本
  - BT 只读预览 / 批量预览里的历史提醒
  - 下载完成后的成人归档与统一保留期清理框架
- 当前新增真相：
  - `tmp_tests/verify_adult_archive_qb_real_smoke.py` 已能以真实 qB Web API + 真实文件系统 + 真实 sidecar 跑到成人归档入口
  - `QbittorrentClient.get_torrent_import_source()` 已改成优先使用 `content_path` 推导真实导入源，不再盲信漂移的 `save_path`
- 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态：`app/bot/private_chat_runtime.py` 当前 `476` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退。
- 当前 real smoke blocker：
  - qB 测试栈目录 `/data/downloads/qb`、`/data/downloads/incomplete-qb` 的当前权限与 compose 里的 `PUID=1000/PGID=1000` 不一致，导致真实 smoke 命中 `file_open ... Permission denied` 和 `storage move failed. mkdir(): Permission denied`
  - `19092` BT Transmission 当前仍不可达，所以这轮先用 qB 路径收口 blocker

## User value

- 成人资源站点、direct magnet 成人链待确认、历史账本和归档 sidecar 的代码主线都已经收口，不再只有“理论上可行”。
- 当前新增的 qB real smoke 探针能把问题直接定位到：
  - repo 侧导入源解析是否正确
  - qB 当前任务真实 `content_path/save_path/state`
  - 测试栈目录权限是否漂移
- 这让后续不再需要在“代码问题”与“测试环境问题”之间来回猜。

## Only do

- 继续收口当前主线时，只做真实 smoke blocker 相关的小闭环：
  - qB real smoke 探针补稳与证据落盘
  - qB 下载目录权限 / 路径漂移 blocker 文档化
  - BT / qB 测试栈就绪条件与 repo 真相保持一致
- direct magnet 继续先问链路，不放宽成自动成人 BT。

## Do not do

- 不把 direct magnet 默认改成成人 BT 自动直投。
- 不把 qB 目录权限问题伪装成代码绿灯，也不靠 mock 掩盖真实 smoke 红灯。
- 不把动漫 BT 再拉回主线；动漫继续走 PT 链。
- 不把这一步扩成浏览器自动化、登录态站点、CAPTCHA 或通用爬站平台。

## Done when

当前这条 **成人 BT 专线真实 smoke blocker 收口** 主线满足：

1. `tmp_tests/verify_adult_archive_qb_real_smoke.py` 能稳定产出真实证据，不再只剩随机现场日志。
2. qB 导入源解析、当前 `content_path/save_path/state` 和宿主机实际文件路径的关系已写成当前真相。
3. 如果测试栈权限修好，qB real smoke 可直接复跑；如果没修好，blocker 也能被一次性定位到目录权限。
4. `make quality`、相关 focused tests 和当前可跑的 smoke 探针结果都已同步到文档。

## After this step

1. 如果本机先修好 qB 下载目录权限，优先重跑 `tmp_tests/verify_adult_archive_qb_real_smoke.py`，拿到通过态证据。
2. 如果 `19092` BT Transmission 恢复可达，再补一轮 BT Transmission 侧的成人归档真实 smoke。
3. 如果暂时不走质量方向，下一条最保守的新闭环是 `javlibrary` helper 的只读识别补全，但不放宽成自动 dispatch 来源。
