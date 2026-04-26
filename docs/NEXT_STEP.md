# Next step (v353)

## Current goal

- 当前主线已从 **成人 BT 专线真实 smoke blocker 收口** 切到 **成人 BT 专线第二条真实 smoke 收口**。
- 当前代码侧与 qB smoke 侧已保持完成态：
  - 成人 BT 站点优先、Prowlarr 成人 PT 补充
  - 成人内容 ID 识别与历史账本
  - BT 只读预览 / 批量预览里的历史提醒
  - 下载完成后的成人归档与统一保留期清理框架
- 当前新增真相：
  - `tmp_tests/verify_adult_archive_qb_real_smoke.py` 已以真实 qB Web API + 真实文件系统 + 真实 sidecar 跑通“归档 -> 保留期清理”
  - `QbittorrentClient.get_torrent_import_source()` 已改成优先使用 `content_path` 推导真实导入源，不再盲信漂移的 `save_path`
- 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态：`app/bot/private_chat_runtime.py` 当前 `476` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退。
- 当前下一条缺口：
  - 成人归档 sidecar 还缺 BT Transmission 侧的第二条真实 smoke 证据
  - `19092` 当前在用户 shell 中可返回 `409 + X-Transmission-Session-Id`，但本轮 Codex shell 里的 probe 仍连续 5 次 `All connection attempts failed`，需要继续收口当轮可达性真相

## User value

- 成人资源站点、direct magnet 成人链待确认、历史账本和归档 sidecar 的代码主线都已经收口，不再只有“理论上可行”。
- 当前已经拿到第一条真实证据：
  - qB 成人归档成功
  - 保留期清理成功
  - `adult_content_registry` 状态从 `archived_present` 走到 `archived_deleted`
- 下一步只需要再补 BT Transmission 侧证据，就能把“成人归档 sidecar 不是单下载器偶然成立”这件事压实。

## Only do

- 继续收口当前主线时，只做第二条真实 smoke 相关的小闭环：
  - BT Transmission `19092` 当轮可达性复验
  - `tmp_tests/verify_bt_transmission_rpc_probe.py` 这类无副作用 probe 先把波动写成证据
  - 成人归档 / 保留期清理在 BT Transmission 侧的真实 smoke 或 blocker 证据
  - 文档、测试环境和当前真实探针结果保持一致
- direct magnet 继续先问链路，不放宽成自动成人 BT。

## Do not do

- 不把 direct magnet 默认改成成人 BT 自动直投。
- 不把 qB 已通过的真实 smoke 当成“所有下载器都已验证”。
- 不把动漫 BT 再拉回主线；动漫继续走 PT 链。
- 不把这一步扩成浏览器自动化、登录态站点、CAPTCHA 或通用爬站平台。

## Done when

当前这条 **成人 BT 专线第二条真实 smoke 收口** 主线满足：

1. qB real smoke 继续保持通过态，可稳定复跑。
2. `19092` BT Transmission 的当轮可达性已写成当前真相，不再混用旧结论。
3. 成人归档 sidecar 在 BT Transmission 侧拿到通过态证据，或 blocker 被一次性定位到环境而不是代码。
4. `make quality`、当前 focused tests 和真实 smoke 结果都已同步到文档。

## After this step

1. 如果 `19092` BT Transmission 侧 smoke 也收口，下一条最保守的新闭环是 `javlibrary` helper 的只读识别补全，但不放宽成自动 dispatch 来源。
2. 如果 `19092` 继续波动，就先用 `tmp_tests/verify_bt_transmission_rpc_probe.py` 固化失败证据，而不是继续手工撞环境。
