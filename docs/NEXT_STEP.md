# Next step (v360)

## Current goal

- 当前主线 **BT 只读候选相关性保护** 已完成；若继续施工，默认切到 **BT 只读 helper 介入时机 / 只读截断策略继续收窄**。
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
  - BT 只读排序 / 展示保护当前也已收口：
    - `offkab / sukebei.nyaa.si / javbus.com / tokyotosho.info` 这类来源别名会映射到既有站点优先级
    - 非 exact-id 只读查询会先按标题相关性排序，再回退到站点优先级 / 做种数
    - exact-id 查询会优先展示标题表面带明确番号的候选
    - 同一番号的多候选只显示一次历史提示
  - BT 只读候选相关性保护当前也已收口：
    - exact-id helper 相关候选会在 `bt搜` top-N 和 `bt批量` 默认预览切片前前置
    - `bt批量` 显式 selection 当前复用同一 helper-aware 顺序，不再和默认预览语义漂移
    - chat 缓存当前会跟随同一 helper-aware 顺序，但 helper-only 字段仍不会写进 `candidate_mapping`
    - 单候选无关结果与显式选中的无关候选当前都不会再兜底贴 helper
    - helper title overlap 当前会过滤 `collection / compilation / edition / complete` 这类 generic token，减少只靠泛噪声词命中的误贴
    - `app/services/bt_read_only_helper_selection.py` 当前承接 helper relevance 选择逻辑，`search_media.py` 不继续堆同类判断
- 当前新增真相：
  - `DOWNLOADER_INSTANCES` 当前可选第 5 段 `dispatch_download_dir`，可把下载器 API 投递路径和宿主机导入路径分开
  - 路由层当前会在导入查询时优先恢复任务真相里的 host `download_dir`
  - `tmp_tests/verify_adult_archive_bt_real_smoke.py` 当前会先清理同 hash 旧任务，再用 `/downloads/complete` 投递，已稳定跑通“归档 -> 保留期清理”
- 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态：`app/bot/private_chat_runtime.py` 当前 `476` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退。
- 当前下一条缺口：
  - helper relevance 当前已不再因为单候选兜底或 `collection / compilation / edition / complete` 这类 generic overlap 误贴；若后续还有边界噪声，需要继续围绕更窄 token/截断 guard 收窄 helper 介入时机
  - 后续若继续收口，只能先做更窄的 focused tests / guard，不能放宽成 helper 写真相或自动 dispatch

## User value

- 成人资源站点、direct magnet 成人链待确认、历史账本和归档 sidecar 当前都不再停留在“理论上可行”。
- 当前两条真实下载器证据都已拿到：
  - qB 成人归档成功，保留期清理成功
  - BT Transmission 成人归档成功，保留期清理成功
- `javlibrary` exact-id helper 已经把“手动只读探索时的最小补全字段”补齐。
- 当前 BT 只读候选相关性保护已经把 top-N / 默认预览 / 定点预览 / 缓存顺序上的 helper 相关性回退风险收口，并额外压掉了单候选兜底误贴与 generic overlap 误贴；如果继续推进，也只应该收窄 helper 介入时机或只读截断策略，不放宽自动 dispatch 边界。

## Only do

- 继续沿当前主线时，只做 **BT 只读 helper 介入时机 / 只读截断策略继续收窄** 这条更窄的小闭环：
  - 优先补 focused tests、helper entry guard 和只读截断回退保护
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

当前这条 **BT 只读 helper 介入时机 / 只读截断策略继续收窄** 主线满足：

1. 新发现的边界噪声若需要处理，必须先有 focused regression tests，且只改 helper 介入时机或只读截断，不改审批真相。
2. `javlibrary` helper 继续保持 exact-id only、BT-only、read-only；helper-only 字段仍不写 `candidate_mapping`、待确认下载或 downloader dispatch 真相。
3. `make quality`、相关 focused tests 和文档都已同步。
4. 现有 qB / BT Transmission 成人归档真实 smoke 通过态不回退。

## After this step

1. 如果 helper 介入时机 / 截断策略也没有更多证据需要继续收窄，就暂停这条成人 BT 只读支线，切回更高风险的质量债。
2. 如果后续仍想扩大成人识别覆盖，优先继续加 focused tests 和只读证据，不要先扩成自动 dispatch。
