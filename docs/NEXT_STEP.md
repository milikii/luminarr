# Next step (v357)

## Current goal

- 当前主线已从 **成人标题归一化回归保护** 切到 **BT 只读排序 / 展示保护**。
- 当前完成态保持：
  - 成人 BT 站点优先、Prowlarr 成人 PT 补充
  - 成人内容 ID 识别与历史账本
  - BT 只读预览 / 批量预览里的历史提醒
  - 下载完成后的成人归档与统一保留期清理框架
  - qB 成人归档真实 smoke 通过
  - BT Transmission 成人归档真实 smoke 通过
  - `javlibrary` 当前已落成 **BT-only read-only exact-id helper**：
    - 只在 `bt搜` / `bt批量` 展示路径补 `display_id / category / title`
    - helper-only 字段不会进入 `candidate_mapping`、待确认下载或 downloader dispatch 真相
  - 成人标题归一化回归保护当前也已收口：
    - 全角 / 变体分隔符输入会先归一化后再做 adult id 识别
    - 常见 uncensored 前缀别名会收口到同一 `normalized_content_id`
    - `一本道 / カリビアンコム / 天然むすめ / パコパコママ / 東京熱` 这类本地化站点别名会先映射回既有 exact-id 规则
    - 常见分辨率 / 编码 / 字幕 / 流出噪声词会在 exact-id 提取前先剥离
    - keyword-only 成人分类猜测不会再写进 BT 候选真相、待确认上下文或 JavLibrary helper 入口
    - JavLibrary helper 当前只会补到仍与当前 exact-id 相关的只读候选
    - 只读展示会压掉仅空格 / 连接符差异的重复 helper 标题
- 当前新增真相：
  - `DOWNLOADER_INSTANCES` 当前可选第 5 段 `dispatch_download_dir`，可把下载器 API 投递路径和宿主机导入路径分开
  - 路由层当前会在导入查询时优先恢复任务真相里的 host `download_dir`
  - `tmp_tests/verify_adult_archive_bt_real_smoke.py` 当前会先清理同 hash 旧任务，再用 `/downloads/complete` 投递，已稳定跑通“归档 -> 保留期清理”
- 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态：`app/bot/private_chat_runtime.py` 当前 `476` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退。
- 当前下一条缺口：
  - BT 只读结果 / 批量预览当前虽然已补最小 helper 展示保护，但排序与展示回退仍主要靠已有格式化逻辑和现有 BT 候选顺序
  - 后续若继续收口，只能先做更窄的 focused display / ordering guard，不能放宽成 helper 写真相或自动 dispatch

## User value

- 成人资源站点、direct magnet 成人链待确认、历史账本和归档 sidecar 当前都不再停留在“理论上可行”。
- 当前两条真实下载器证据都已拿到：
  - qB 成人归档成功，保留期清理成功
  - BT Transmission 成人归档成功，保留期清理成功
- `javlibrary` exact-id helper 已经把“手动只读探索时的最小补全字段”补齐。
- 当前切到更窄的 BT 只读排序 / 展示保护，可以继续在不放宽自动 dispatch 边界的前提下，降低只读预览排序漂移、重复信息和展示回退的风险。

## Only do

- 继续沿当前主线时，只做 **BT 只读排序 / 展示保护** 这条更窄的小闭环：
  - 优先补 focused tests、排序 guard 和只读展示回退保护
  - 只服务成人 BT 支线，不进 PT 主链
  - 不放宽 `javlibrary` 的 exact-id only / BT-only / read-only 边界
  - 保持当前 qB / BT Transmission 真实 smoke 结果、测试环境与文档一致
- direct magnet 继续先问链路，不放宽成自动成人 BT。

## Do not do

- 不把 direct magnet 默认改成成人 BT 自动直投。
- 不把 `javlibrary` helper 放宽成自动 dispatch、自动确认、非 exact-id helper 或通用爬站平台。
- 不把动漫 BT 再拉回主线；动漫继续走 PT 链。
- 不把这一步扩成浏览器自动化、登录态站点、CAPTCHA 或通用爬站平台。

## Done when

当前这条 **BT 只读排序 / 展示保护** 主线满足：

1. BT 只读结果 / 批量预览的排序、重复信息压制和展示回退都有 focused regression tests 保护。
2. `javlibrary` helper 继续保持 exact-id only、BT-only、read-only，不写审批真相。
3. `make quality`、相关 focused tests 和文档都已同步。
4. 现有 qB / BT Transmission 成人归档真实 smoke 通过态不回退。

## After this step

1. 如果 BT 只读排序 / 展示保护也收口，再看是否还有必要补更窄的 read-only candidate relevance guard。
2. 如果后续仍想扩大成人识别覆盖，优先继续加 focused tests 和只读证据，不要先扩成自动 dispatch。
