# TASKS.md

> 本清单基于 2026-04-28 当前仓库代码、测试和运行结果整理。分成“当前已知问题”“高优先工程债”“后续能力补齐”三类，避免把健康功能误写成故障。

## 当前验证快照

- `make verify-adult-bt-wedge`：通过
- `make verify-mainline`：通过
- `make quality`：通过
- `adult BT minimum wedge`：已完成并已推送到 `main`
- Telegram 人工 smoke：应用已启动，等待当前会话验证
- 下一条唯一主线：扩展 BT subscription 边界（优先锁定 raw BT subscription 的最小 contract，继续保持 confirm 边界）
- 结论：当前 P0 阻断已清空；后续按 P1 / P2 顺序推进，不回切 `services` 结构降本主线

## P0 已完成

- [x] 修复 docs gate：让 `AGENTS.md` 与 `tests/test_cleanup_docs_consistency.py` 的入口文档约定重新一致，至少补齐 `docs/INDEX.md` 等活跃文档引用，恢复 `make quality` 通过。

- [x] 重新定义 active docs root 预算：当前测试要求 `docs/*.md <= 15`，但项目现在已经显式需要 `PRD.md`、`ARCHITECTURE.md`、`TASKS.md` 等基础文档；需要决定是归档两份次级文档，还是更新 docs gate 的“活跃文档上限”规则。

## P1 高优先工程债

- [x] 解耦启动硬依赖（方案 A）：`app/config.py` 当前无论是否启用其他渠道或多下载器，都会硬要求 `PROWLARR_*` 与 legacy `TRANSMISSION_BASE_URL`；需要改成 capability contract 驱动的配置校验，并同步收口 `app/main.py` 装配、runtime unavailable guard、focused tests 和操作文档。`TELEGRAM_BOT_TOKEN` 本轮继续保持当前宿主必填，不在这里偷渡宿主解耦。

- [x] 解耦 sidecar 宿主：`app/bot/telegram_sidecar_runtime.py` 让 Feishu、WeCom、personal WeChat、自动导入和 BT 订阅 scheduler 都挂在 Telegram `Application` 生命周期下；如果要支持“非 Telegram 也能独立运行”，这里需要先拆。

- [x] 继续收口超大业务文件：`app/services/add_to_downloader.py`、`app/services/import_to_library.py`、`app/services/manage_bt_subscription.py`、`app/services/search_media.py`、`app/services/cleanup_downloaded_source.py`、`app/services/subtitle_translation_support.py` 仍然过大，阅读和改动成本高，当前主线仍应优先做单消费者状态壳、重复 helper 和局部职责拆分。

- [x] 明确 Feishu 可选依赖策略：代码里通过 `lark_oapi` 启动 Feishu 长连接，但 `requirements.txt` 没有显式声明这项依赖；需要决定是补到安装依赖、拆成 extras，还是在文档里把“额外安装步骤”写死。

- [x] 清理当前依赖告警：`make verify-mainline` 虽然通过，但会持续打印 `lark_oapi` / `websockets` 相关 deprecation warnings；需要决定是升级、锁版本，还是局部隔离这条可选链路。

## P2 已实现但还不完整的能力

- [x] 锁定并落地首个 non-Telegram 一等公民最小画像：`Feishu-only` 文本私聊现在可在无 `TELEGRAM_BOT_TOKEN` 时独立启动，并对当前入站消息即时回复；后台主动通知仍明确不在本轮范围。

- [x] 落地 non-Telegram 第二阶段 `WeCom-only` 独立宿主：当前在无 `TELEGRAM_BOT_TOKEN`、但具备 WeCom 三元组时可以独立启动并通过 webhook 收到消息、同步回包。

- [x] 继续补齐 non-Telegram 后台主动通知所需的可逆会话真相：当前已落地运行态联系人注册表，但 `btsub` / 下载完成等后台通知仍未具备对 non-Telegram 会话的独立可发回路。

- [x] 强化 watchlist 到自动化链的衔接：当前已新增显式 `watchlist sync` / `想看 同步`，会把想看条目按相同 `chat_id` / `title` / `year` / `media_kind` 原子同步进 `btsub`，不触发自动下载，也不会在失败时残留部分成功。

- [ ] 扩展 BT subscription 边界：当前 `btsub` 已有手动命令和后台 tick，但仍是最小实现，不支持 raw BT 订阅、不支持自动确认、通知渠道也主要围绕当前宿主链路。

- [ ] 丰富多渠道交互形态：当前四个渠道统一落在文本私聊基线，尚未把卡片、按钮回调、富媒体消息当作主产品面能力。

## P3 文档与运维改进

- [ ] 为 `docs/PRD.md`、`docs/ARCHITECTURE.md`、`docs/TASKS.md` 建立持续维护规则，避免再次出现“代码能力很多，但基础项目文档缺位”的冷启动成本。

- [ ] 把运行时外部依赖统一列清：`ffmpeg` / `ffprobe`、personal WeChat 登录态目录、Feishu 可选 SDK、WeCom 回调端口与反代要求目前分散在多处文档，后续应收敛成单一运维真相页。

- [ ] 继续保持“文档 gate 可执行”的纪律：当前仓库已经把 README / INDEX / STATUS / NEXT_STEP / AGENTS 的一致性写成测试，后续新增入口文档时应同步补 gate，而不是只补正文。
