# Next step (v198)

## Current goal

- 当前唯一主线：**four-channel cleanup verification baseline（已完成）**
- 当前窗口：`2026-04-05 to 2026-04-12`
- 详细台账和证据统一写在 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## Source of truth

- 长期边界：`docs/DECISIONS.md`
- 当前目标：`docs/NEXT_STEP.md`
- 当前快照：`docs/STATUS.md`
- cleanup 详细窗口规则和证据：`docs/CLEANUP_VERIFICATION_WINDOW.md`
- 知识入口：`README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md`

## Only do

- 完成一个 7 天真实使用验证窗口，不新增任何 cleanup 行为。
- 保持 Telegram / personal WeChat / Feishu / WeCom 四个渠道都可用，且继续共用同一套 shared runtime、workflow、approval、`jobs` 和 SQLite 真相。
- 持续记录窗口起止日期、四渠道真实私聊 smoke 进度、窗口活性、当前结论、最近一次 smoke gate / cleanup 协议回归 / verification docs gate 到 `docs/CLEANUP_VERIFICATION_WINDOW.md`。
- 保持仍在进行中的 cleanup 验证窗口快照和最近一次验证日期同步到当天绝对日期，避免窗口台账和 `docs/STATUS.md` 停留旧日期。
- 保持 cleanup 文档快照继续反映“当前 `.env` 已满足四渠道 smoke 环境键、且在 `app.main` 已运行时本地 `18889/wecom/callback` 已可达、四渠道真实私聊 smoke 已全部补齐”这条最新真相，避免环境 blocker、进程未启动和已完成窗口真相重新混写。
- 保持 cleanup 文档快照也显式写出当前 WeCom tunnel 环境 blocker：`docker` 虽已安装但当前 shell 仍无 `/var/run/docker.sock` 访问权限，且 `cloudflared` 命令尚未安装，避免把 tunnel 失败继续误记成业务代码回归。
- 保持 `docs/GETTING_STARTED.md` 显式区分“WeCom 本地 callback readiness 已就绪”和“WeCom 真实私聊 smoke 证据已完成”，避免把 `400 missing echostr` 探针误读成窗口退出证据。
- 保持 `README.md` 也显式区分“WeCom 本地 callback readiness 已就绪”和“WeCom 真实私聊 smoke 证据已完成”，避免用户只看仓库入口时继续把 readiness 探针误读成退出证据。
- 保持 `README.md` / `docs/GETTING_STARTED.md` 也显式写出 `18889/wecom/callback` 是当前本地已验证 `.env` 的地址，不要让入口文档把它误写成模板默认值。
- 保持 `README.md` / `docs/GETTING_STARTED.md` 也显式写出“若本地改了 `WECOM_WEBHOOK_HOST` / `WECOM_WEBHOOK_PORT` / `WECOM_WEBHOOK_PATH`，WeCom readiness 探针地址也必须跟着当前 `.env` 走”，避免用户把当前样例地址误抄成固定值。
- 保持 `README.md` 当前 next step 段也显式写出 cleanup 四渠道验证窗口已完成，避免入口文档继续停留在“只剩 WeCom 待补”的旧结论。
- 保持 verification docs gate 继续显式校验 `docs/NEXT_STEP.md` 里的 cleanup 完成态文案，避免主线目标页回退成只列退出条件、不写当前完成结论。
- 保持 verification docs gate 继续显式校验 `docs/STATUS.md` 里的 `WeCom 本地入口快照` 文案，避免状态页把本地 readiness 探针写丢。
- 保持 verification docs gate 继续显式校验 `docs/STATUS.md` 里的 `WeCom 探针来源快照` 文案，避免状态页把“当前本地已验证 `.env`”和“.env.example 默认值”的边界写丢。
- 保持 verification docs gate 继续显式校验 `docs/STATUS.md` 里的 `README 缺口快照` 文案，避免状态页把入口页“当前只剩 WeCom 缺口”这句当前总结写丢。
- 保持 verification docs gate 继续显式校验 `docs/STATUS.md` 里的 `NEXT_STEP 缺口快照` 文案，避免状态页把主线目标页“当前只剩 WeCom 缺口”这句当前总结写丢。
- 保持 verification docs gate 继续显式校验 `docs/STATUS.md` 里这组 WeCom 入口/缺口门禁收口快照，确保 `WeCom 本地入口快照`、`WeCom 探针来源快照`、`README 缺口快照`、`NEXT_STEP 缺口快照` 不会只锁住其中一部分。
- 保持 `docs/STATUS.md` 只保留快照，不把窗口详细规则和备注明细抄回去。
- 保持 `README.md` 只同步仓库入口需要知道的当前边界、cleanup 风险和后续路线；窗口逐项证据继续只写在 `docs/CLEANUP_VERIFICATION_WINDOW.md` / `docs/STATUS.md`。
- 保持 `README.md` 当前 next step 的退出条件也显式覆盖 `verification docs gate`，避免用户只看仓库入口时误以为 docs gate 不是 cleanup 验证窗口的正式退出条件。
- 保持 `README.md` 的快速启动入口继续显式写出当前启动硬必填键和“`TMDB_API_KEY` 可空、`DOWNLOADER_INSTANCES` 不能替代 `TRANSMISSION_BASE_URL`”这条真相，避免用户只看仓库入口时按旧配置直觉起服务。
- 保持 verification docs gate 继续显式校验 `README.md` 的十条 cleanup 本地 gate 入口仍写明“不能替代四渠道真实私聊 smoke 证据”，避免用户把本地 pytest / docs gate 误读成真实渠道退出证据。
- 保持历史单体主文档 `Luminarr_v15.md` 不再作为当前知识入口，避免过期总纲和 `README.md -> docs/INDEX.md -> docs/GETTING_STARTED.md -> docs/ARCHITECTURE.md` 这条正式入口重新分叉。
- 保持 `docs/GETTING_STARTED.md` 明确区分“能启动应用”和“能补当前 cleanup 验证窗口四渠道真实私聊 smoke 证据”的前置条件，避免把本地回归误当成真实渠道验证。
- 保持 `docs/GETTING_STARTED.md` 对“Telegram + 本地 Transmission/Emby 已启动”这条最小 bring-up 路径写出明确的 `.env` 变量组合，避免用户拿着 token 和本地测试栈仍然要自己拼配置。
- 保持 `.env.example` 用中文详细说明每个变量的作用、默认值语义，以及“只为启动最小本地测试”时真正必填的变量集合，避免把配置模板误读成完整渠道准备状态。
- 保持 `.env.example` 对 `DOWNLOADER_INSTANCES` / `PT_DOWNLOADER` / `BT_DOWNLOADER` / `RAW_BT_DESTINATIONS` / `BT_WEB_SOURCES` / `FEISHU_*` / `WECOM_*` 继续写清中文作用、取值格式和默认语义，避免用户拿到 token 后仍不知道其他必需字段该填什么。
- 保持 verification docs gate 继续显式校验 `.env.example` 里的 `PROWLARR_API_KEY` / `TMDB_API_KEY` / `DOWNLOADER_INSTANCES` / `FEISHU_APP_ID` / `FEISHU_APP_SECRET` / `FEISHU_ENCRYPT_KEY` / `WECOM_TOKEN` / `WECOM_ENCODING_AES_KEY` / `WECOM_RECEIVE_ID`，避免最小 bring-up 必填键和四渠道真实 smoke 键从模板说明里漂走。
- 保持 `.env.example` / `docs/GETTING_STARTED.md` 对 `TELEGRAM_BOT_TOKEN`、`TMDB_API_KEY`、`TRANSMISSION_BASE_URL`、`DOWNLOADER_INSTANCES`、`PT_DOWNLOADER` / `BT_DOWNLOADER` 默认语义，以及 Feishu / WeCom 三元组 all-or-none 约束的中文说明与 `app/config.py` 当前真相一致，避免用户按旧文档配出启动失败的 `.env`。
- 保持 `.env.example` / `docs/GETTING_STARTED.md` / `README.md` 也显式写出 `OUTBOUND_PROXY_URL` 的使用边界：Telegram / TMDB / Fanart / BT 外站 / 字幕翻译走代理，Transmission / Emby / Prowlarr 继续直连，避免把代理错误扩到本地联调链路。
- 保持 `docs/STATUS.md` / `README.md` 继续显式写出 Feishu 当前已支持 `FEISHU_INBOUND_MODE=long_connection`，且该模式只要求 `FEISHU_APP_ID + FEISHU_APP_SECRET`，避免入口文档仍停在“Feishu 永远必须三元组齐全”的旧真相。
- 保持 Feishu 长连接在正常停机时不要把关闭过程误报成 `[Feishu 长连接启动失败]`、`ConnectionClosedOK` traceback 或 `Event loop is closed` traceback，避免 bring-up/cleanup 验证证据把正常 shutdown 误记成启动回归。
- 保持 `docs/TEST_ENV.md` / `README.md` / `docs/STATUS.md` 对本地双 Transmission 测试栈保持一致，显式反映 BT Transmission `http://127.0.0.1:19092` 和 `/data/downloads/tr-bt`，避免 PT / BT 本地联调入口继续分叉。
- 保持 BT Transmission 测试栈继续绑定新的 `config/transmission-bt-stack` 配置目录，并按 LinuxServer 官方支持的 `/downloads/complete` / `/downloads/incomplete` / `/watch` 挂载方式初始化，避免复用旧 `config/transmission-bt` 里已写入默认 `/downloads/...` 的脏 `settings.json`，导致 `19092` 端口起不来却被误判成 compose 配置回退。
- 保持 `docs/STATUS.md` / `README.md` 继续显式写出 personal WeChat `微信登录` 当前回传的是 PNG 二维码图片，不再是 SVG 文件，避免用户入口和 Telegram 发送行为重新分叉。
- 保持 `Makefile` 同时提供独立的四渠道 cleanup smoke gate 入口和当前 cleanup 验证窗口的一键 gate 入口，避免把 smoke gate、cleanup 聚合回归和 docs gate 混成一条不透明命令。
- 保持 `Makefile` 明确暴露 `test-cleanup-docs-gate`，让 cleanup verification docs gate 和普通 `test-docs` 分开，避免把 docs consistency gate 误当成当前 cleanup 窗口的完整文档 gate。
- 保持 `Makefile` 明确暴露 `test-cleanup-service-not-ready`，让 cleanup service-not-ready observability 有独立 gate，避免这条专项 smoke 只能从 `docs/STATUS.md` 里的底层 pytest 命令回推。
- 保持 `Makefile` 明确暴露 `test-cleanup-telegram`，让 Telegram cleanup 入口回归有稳定入口，避免 `docs/STATUS.md` 里的单渠道回归仍只能靠底层 pytest 命令手敲。
- 保持 `Makefile` 明确暴露 `test-cleanup-personal-wechat`，让 personal WeChat cleanup 入口回归有稳定入口，避免这个私聊渠道的 cleanup 回归仍只能从聚合 gate 里拆命令。
- 保持 `Makefile` 明确暴露 `test-cleanup-feishu`，让 Feishu cleanup 入口回归有稳定入口，避免这个私聊渠道的 cleanup 回归仍只能从聚合 gate 里拆命令。
- 保持 `Makefile` 明确暴露 `test-cleanup-wecom`，让 WeCom cleanup 入口回归有稳定入口，避免这个私聊渠道的 cleanup 回归仍只能从聚合 gate 里拆命令。
- 保持 `Makefile` 明确暴露 `test-cleanup-feishu-webhook`，让 Feishu webhook cleanup 入口回归有稳定入口，避免这个加密 webhook 路径只能从文档示例间接回推。
- 保持 `Makefile` 明确暴露 `test-cleanup`，让 cleanup 聚合回归有稳定入口，避免窗口 gate 仍只能从 `test-cleanup-window` 反推第二段命令。
- 保持 `README.md` / `docs/GETTING_STARTED.md` 继续提供无 `make` 环境下的等价一行 pytest 备用命令，至少显式覆盖 `test-cleanup-service-not-ready`、`test-cleanup-telegram`、`test-cleanup`、`test-cleanup-docs-gate` 和 `test-cleanup-window`，避免把 Makefile 当成当前 cleanup 窗口 gate 的唯一入口。
- 保持 verification docs gate 继续显式校验 `test-cleanup-window` 仍按 `smoke gate -> cleanup 聚合回归 -> verification docs gate` 顺序执行，且 `docs/GETTING_STARTED.md` 里的无 `make` 备用命令与这三段 Makefile 入口保持一致，避免窗口 gate 入口拆成多份后互相漂移。
- 保持 `docs/GETTING_STARTED.md` / `docs/TEST_ENV.md` 对 Transmission / Emby 本地测试栈的 compose 文件位置、启动命令和配置目录位置保持一致，避免把不存在的目录误写成 compose 根目录。
- 保持 `docs/GETTING_STARTED.md` / `docs/TEST_ENV.md` 的 Transmission 健康检查继续使用 `curl -si` 读取 `X-Transmission-Session-Id` 响应头，避免把正常的 `409 Conflict` 误判成服务不可达。
- 保持 `docs/STATUS.md` 里的 tests / cleanup service / compile check / docs consistency check 都带绝对日期，避免这些本地验证快照比 smoke / docs gate 更难判断是否过期。
- 保持仓库里有显式的 cleanup 验证快照同步工具，把固定验证命令的最新结果批量写回 `docs/STATUS.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md`，避免 7 天窗口里的验证快照继续靠人工抄写而漂移。
- 保持四渠道真实私聊 cleanup smoke 证据后续统一落到同一套 `cleanup 私聊 smoke` 日志协议里，至少固定 `date/channel/action/query/reply_head` 这组字段，避免 Telegram / personal WeChat / Feishu / WeCom 各自打印不同格式、后面无法稳定回填窗口台账。
- 保持 `app/main.py` 启动时把真实私聊 cleanup smoke 追加落盘到 `logs/cleanup-private-chat-smoke.log`，避免真实 smoke 只留在 stdout、`sync-cleanup-doc-snapshots` 扫不到仓库证据。
- 保持 `sync-cleanup-doc-snapshots` 把 Telegram `getMe` 就绪快照一起写回 `docs/STATUS.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md`，避免 bot token 可用性继续停留在口头说明、无法区分“凭据不可用”和“真实私聊证据待补”。
- 保持 verification docs gate 继续显式校验 `sync-cleanup-doc-snapshots` 这条新同步入口在 `Makefile` 和 `docs/GETTING_STARTED.md` 里保持一致，避免刚加的 docs 维护路径下一轮又重新分叉。
- 保持 verification docs gate 继续显式校验 `telegram_bot_api` 已接进 `sync-cleanup-doc-snapshots`、`docs/STATUS.md` 和 `docs/CLEANUP_VERIFICATION_WINDOW.md`，避免 Telegram 真实 smoke 的外部可用性快照重新退回手工说明。
- 保持 `sync-cleanup-doc-snapshots` 在 Telegram `getMe` 返回 401/403 时稳定写成 `telegram bot api rejected token`，不要和网络不可达混写成 `unreachable`，避免窗口快照把坏 token 误记成网络波动。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续单独锁住 Telegram Bot API 的 `rejected token` / `unreachable` 分类，避免后续把坏 token 和网络不可达重新混写成同一类 blocker。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续单独锁住非 401/403 的 Telegram Bot API HTTP 错误会归成 `unreachable`，避免 5xx / 网关异常被误写成坏 token。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续单独锁住 Telegram Bot API 坏 JSON 响应会归成 `unreachable`，避免异常响应体被误写成坏 token 或 ready。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续单独锁住 Telegram Bot API 底层 `OSError` 会归成 `unreachable`，避免 socket/SSL 级网络异常直接打断 cleanup 文档快照同步。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续单独锁住 `telegram bot token missing` 分支，避免最基础的凭据缺失态从 Telegram Bot API 快照门禁里漂走。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续单独锁住“仓库 `.env` 不可读且无其他 token 来源时，`telegram_bot_api` 仍返回 `telegram bot token missing`”这条 end-to-end 路径，避免 `.env` 读取容错只停在 helper 层。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续单独锁住“Windows env 探测抛 `OSError` 且无其他 token 来源时，`telegram_bot_api` 仍返回 `telegram bot token missing`”这条 end-to-end 路径，避免 Windows env 调用异常容错只停在 helper 层。
- 保持 `sync-cleanup-doc-snapshots` 读取仓库 `.env` 时先去掉首尾成对引号，再参与 `telegram_bot_api` / `env_readiness` 快照判断，避免 `"token"` 这类配置被当成带引号字面量发出去。
- 保持 `sync-cleanup-doc-snapshots` 读取当前 shell 环境变量值时也先去掉首尾成对引号，避免 `export TELEGRAM_BOT_TOKEN='"token"'` 这类当前会话配置直接盖过后面的正确值。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续单独锁住“当前 shell 里的带引号 `TELEGRAM_BOT_TOKEN` 会先去引号再请求 Telegram Bot API”这条快照路径，避免 shell token 去引号逻辑只停在 helper 单测。
- 保持 `sync-cleanup-doc-snapshots` 读取 Windows `cmd.exe /c set` 输出时按大小写不敏感匹配键名，避免 `telegram_bot_token=...` 这类输出被误判成缺失环境变量。
- 保持 `sync-cleanup-doc-snapshots` 读取 Windows `cmd.exe /c set` 输出时也先去掉值首尾成对引号，避免 `TELEGRAM_BOT_TOKEN=\"token\"` 这类配置被当成带引号字面量继续写进快照。
- 保持 cleanup verification docs sync 在调用 Windows `cmd.exe /c set` 自身抛 `OSError` 时按“Windows env 缺失”继续降级，不让单次 Windows 环境探测异常直接打断 `env_readiness` / `telegram_bot_api` 快照链。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续单独锁住“Windows env 小写键名 + 带引号 `TELEGRAM_BOT_TOKEN` 会先归一化再请求 Telegram Bot API”这条快照路径，避免 Windows token 去引号逻辑只停在 helper 单测。
- 保持 `sync-cleanup-doc-snapshots` 写回 docs 的 `env_readiness` / `telegram_bot_api` command display 也同步反映“.env 去首尾引号 + Windows env 键名大小写不敏感”这两条当前真相，避免状态页展示仍停在旧逻辑。
- 保持 `docs/STATUS.md` 里的 “docs command display 同步快照” 摘要文案也同步覆盖“当前 shell / .env / Windows env 值去首尾引号、Windows env 键名大小写不敏感、env readiness Windows 值级判定”这组当前真相，避免状态页总述快照落后于已落地行为。
- 保持 `sync-cleanup-doc-snapshots` 写回 docs 的 `env_readiness` command display 里，Windows env 这一段也按“大小写不敏感键名 + 去首尾引号后的非空值”判定 `set/missing`，避免状态页把空值 Windows 环境变量误读成已就绪。
- 保持 `sync-cleanup-doc-snapshots` 写回 docs 的 `telegram_bot_api` command display 也同步反映“当前 shell / .env / Windows env 值去首尾引号 + Windows env 键名大小写不敏感”这整条当前真相，避免状态页继续展示旧的 token 解析路径。
- 保持 `sync-cleanup-doc-snapshots` 写回 docs 的 `env_readiness` / `telegram_bot_api` command display 继续保留可执行的 `strip('\"\'')` 转义片段，避免状态页命令示例被写坏成不可运行的引号拼接。
- 保持 `sync-cleanup-doc-snapshots` 写回 docs 的 `env_readiness` command display 也显式反映“当前 shell 环境变量值先去首尾引号再判空”这条当前真相，避免状态页继续展示旧的 shell 判空逻辑。
- 保持 verification docs gate 继续显式校验 `env_readiness` / `local_smoke_evidence` 两条新同步键已经接进 `sync-cleanup-doc-snapshots`，并和 `docs/STATUS.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md` 的对应快照行保持一致，避免环境 blocker 快照重新退回手工抄写。
- 保持 `env_readiness` 在本地 runtime/import 已就绪但四渠道 smoke 仍未齐时，直接写出缺失渠道列表，避免窗口台账继续只报 `incomplete` 却不说明下一步该补哪条渠道。
- 保持 `env_readiness` 在四渠道 smoke 环境不完整时按真实缺失渠道组动态写出 `missing channels: ...`，并继续显式写明 `personal_wechat login state not checked`，避免把 personal WeChat 误判成已经由 `.env` 覆盖就绪。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续单独锁住 `env_readiness` 的 `four-channel cleanup smoke env ready` 完成态分支，避免四渠道键已齐时状态页仍误报成 incomplete。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续单独锁住 `env_readiness` 的 `local runtime env ready; import/refresh env incomplete` 中间态分支，避免 Emby/import 缺口被误写成别的 blocker。
- 保持 cleanup verification docs sync 在仓库 `.env` 存在但不可读时按“该来源缺失”继续降级，不让单个 `.env` 权限问题直接打断 `env_readiness` / `telegram_bot_api` 快照链。
- 保持 `local_smoke_evidence` 在命中窗口期 `[cleanup 私聊 smoke]` 日志时同时给出 `found channels + missing channels`，四渠道齐全后改成 `all channels covered`，没命中时显式列出缺失渠道，避免仓库证据快照不能直接说明当前窗口还差什么。
- 保持 cleanup verification docs sync 在遇到单个不可读的 smoke 日志文件时跳过该文件，并继续统计其余可读证据，避免一个坏日志把整个窗口文档同步链打断。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续单独锁住 `local_smoke_evidence` 在同一日志文件夹里遇到 non-UTF8 脏字节时，仍能保留同文件中有效的 `[cleanup 私聊 smoke]` 行，避免脏日志字节把仓库证据统计打断。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续直接锁住 `sync_documents()` 在 non-UTF8 脏字节日志下仍能把命中渠道写进 `Channel progress`，避免 helper 级通过但真实文档回写链丢证据。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续单独锁住 `local_smoke_evidence` 在同一日志文件里遇到损坏的 `[cleanup 私聊 smoke]` payload 行时，仍会忽略坏行并保留同文件中的合法协议行，避免单条坏 payload 污染仓库证据统计。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续直接锁住 `sync_documents()` 在同一日志文件混入损坏 cleanup smoke payload 行时，仍会忽略坏行并把合法渠道写进 `Channel progress`，避免 helper 级通过但真实文档回写链丢证据。
- 保持 cleanup 窗口仍标记为进行中时，`local_smoke_evidence` / `Channel progress` 继续接受“开始日期之后、当前快照日期之前”的真实 smoke 证据，不把 `最早可结束日期` 误当成后续补证的硬截止线。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续单独锁住“晚于当前快照日期的 cleanup smoke 日志不会被算进 `local_smoke_evidence`”这条门禁，避免未来日期日志被误回填成当前窗口证据。
- 保持 `docs/CLEANUP_VERIFICATION_WINDOW.md` 的 `Update rule` 也直接写明“进行中窗口的补证上界跟随当前结论快照日期”，避免实现已放开补证、但窗口规则文字仍停留在旧理解。
- 保持 cleanup 文档同步工具继续按渠道收集“窗口内最近一次真实 smoke 日期”，为后续 `Channel progress` 自动同步提供稳定输入，避免接表格时又回头重复扫描原始日志。
- 保持 `sync-cleanup-doc-snapshots` 继续按固定四渠道顺序自动重写 `Channel progress` 表：命中渠道写 `已完成 + 最近日期`，未命中渠道保持 `待验证` 和窗口开始日锚点，避免真实 smoke 一补完又要手工回填表格。
- 保持 verification docs gate 继续显式校验 `Channel progress` 自动同步不会吞掉 `Verification evidence`、`PT 做种 guardrail 评估` 和 `Update rule` 后续章节，避免窗口台账被错误截断成只剩进度表。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续直接跑最小 `sync_documents()` 回写样例，锁住整条文档同步路径在重写 `Channel progress` 后仍保留三段章节标题，避免 helper 通过但真实写回路径继续漂移。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续直接锁住 `sync_documents()` 在日志乱序时仍按 Telegram / personal WeChat / Feishu / WeCom 固定顺序重写 `Channel progress`，避免窗口台账每次回写都按日志发现顺序抖动。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续直接锁住 `sync_documents()` 在同一渠道命中多条窗口期真实 smoke 日志时取最近绝对日期，避免 `Channel progress` 把旧日期写回已完成渠道。
- 保持 `tests/test_cleanup_verification_docs_sync.py` 继续直接锁住 `sync_documents()` 在只有部分渠道完成时，未命中渠道仍保留 `待验证`、`-` 和窗口开始日锚点备注，避免窗口台账把剩余缺口写成空白或旧格式。
- 保持 `tests/test_cleanup_verification_window_doc.py` 继续直接校验当前窗口台账里的 `Channel progress` 行顺序固定为 Telegram / personal WeChat / Feishu / WeCom，避免文档手改时绕过同步器顺序门禁。
- 保持 cleanup verification docs sync 在 WSL 调用 Windows `cmd.exe /c set` 时兼容非 UTF-8 输出，避免当天环境快照因为编码异常停摆。
- 保持 verification docs gate 继续显式校验 `local_smoke_evidence` 只认窗口期 `[cleanup 私聊 smoke]` 日志协议，不把任意 `jobs` / `job_event` / `telegram_updates` 时间戳或普通日志文件日期误算成真实私聊 smoke 证据，避免窗口台账把普通运行痕迹写成退出条件。
- 保持 verification docs gate 继续显式校验 `runtime_process` 已接进 `sync-cleanup-doc-snapshots`、`Makefile` 和 `docs/GETTING_STARTED.md`，并和 `docs/STATUS.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md` 的运行进程快照保持一致，避免“当前有没有运行中的 Luminarr 进程”继续靠手工抄写。
- 保持 `docs/STATUS.md` 把配置真相回归（`tests/test_config.py` 里和当前文档变更直接相关的 focused config checks）也写成带绝对日期的快照，避免配置入口更新后状态页看不到对应验证证据。
- 保持 `docs/STATUS.md` 对本机 Transmission / Emby 测试栈的当前 shell 健康检查结果、Docker 权限 blocker，以及“仓库 `.env` 已具备哪些本地最小运行键、四渠道真实 smoke 还缺哪些 Feishu / WeCom 凭据”写成显式快照，避免把“用户说已经启动 / token 已准备好”误写成当前 shell 已具备完整四渠道真实 smoke 条件。
- 保持 `docs/STATUS.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md` 显式写出“仓库根目录与本地测试目录是否存在可直接启动 Luminarr 的 `.env`、当前是否有运行中的 Luminarr 进程、SQLite / logs 里是否已有窗口期真实私聊 smoke 证据”，避免把“本机服务已启动”误写成“当前仓库里已有可回填的四渠道真实 smoke 记录”。
- 保持 cleanup 验证窗口仍在进行中时，`docs/CLEANUP_VERIFICATION_WINDOW.md` 的 smoke gate / cleanup 协议回归 / verification docs gate 日期，与 `docs/STATUS.md` 的 tests / cleanup service / compile check / docs consistency check 一起滚动到当天绝对日期，避免只更新半套快照。
- 保持 `tests/test_cleanup_cross_channel_smoke.py` 稳定，继续作为四渠道 cleanup discoverability / inspect / execution / rejection guidance / post-cleanup confirmation / mixed-case english cleanup protocol / `chat-scoped task_ref -> jobs -> import correlation` / correlation-query-failure identity retention / missing-structured-import-correlation identity retention 的聚合 smoke gate。
- 保持 `tests/test_telegram_bot.py -k cleanup` 单独覆盖 Telegram cleanup mixed-case 英文 `cleanup / cleanup inspect` 入口路由，避免 Telegram 渠道胶水大小写回退只能等聚合 smoke 才暴露。
- 保持 Telegram cleanup 入口在文本成功回出后继续复用统一的 `[cleanup 私聊 smoke]` 日志协议，并至少带上 `date/channel/action/query/reply_head`，避免第一个接入完成后下一轮又改成 Telegram 专属格式。
- 保持 `tests/test_telegram_bot.py` 单独覆盖 Telegram 入口里的 `cleanup-shortcut` 这类 `chat-scoped task_ref -> jobs -> import correlation` 身份解析，避免主入口把 shortcut 当成普通字符串传下去却绕过 shared runtime 的 chat-scoped lookup。
- 保持 README / STATUS 对 cleanup 聚合 smoke gate 的入口描述也同步覆盖 mixed-case 英文 `cleanup / cleanup inspect` 输入、`job_event` 关联查询失败、缺结构化 `source_path/target_path` 两类 identity retention / rejection guidance，以及 `guard-rejected` rejection guidance，避免入口文档落后于当前 gate。
- 保持 verification docs gate 继续显式校验 `mixed-case english cleanup protocol` 命名观察，避免窗口台账把英文字母大小写输入边界写丢。
- 保持 verification docs gate 继续显式校验 `NEXT_STEP current-window sync`，避免 `docs/NEXT_STEP.md` 里的 `当前窗口` 日期和 `docs/CLEANUP_VERIFICATION_WINDOW.md` 的窗口日期只改一处。
- 保持 verification docs gate 继续显式校验到达最早可结束日期但退出条件未满足时，`docs/STATUS.md` / `docs/CLEANUP_VERIFICATION_WINDOW.md` 同步切成 `已到最早可结束日期，待补退出条件`，避免窗口已经跨过结束日却还停留在 `未到最早可结束日期` 的旧快照。
- 保持 verification docs gate 继续显式校验 `correlation-query-failure observability` 命名观察，避免窗口台账把这类 query failure 可观测性写丢。
- 保持 verification docs gate 继续显式校验 `source-type-unsupported blocked-log observability` 命名观察，避免窗口台账把这类阻断日志可观测性写丢。
- 保持 verification docs gate 继续显式校验 `cleanup-service-not-ready fix-hint observability` 命名观察，避免窗口台账把 cleanup service 未注入时的红色日志和处理建议写丢。
- 保持 `tests/test_cleanup_cross_channel_smoke.py -k service_not_ready` 继续锁住四渠道 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查` 的 cleanup service-not-ready observability，避免单渠道各自通过后，聚合 smoke 仍遗漏跨渠道协议漂移。
- 保持 `tests/test_private_chat_runtime.py` 单独覆盖 shared runtime 直调路径的 cleanup service-not-ready observability，并锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查` 入口变体，避免这条共享入口只能靠四渠道 smoke 或英文带任务引用路径侧面兜底。
- 保持 `tests/test_telegram_bot.py -k "cleanup and service_not_ready"` 单独覆盖 Telegram cleanup service-not-ready observability，避免这个渠道的 cleanup 命令入口只能靠聚合 smoke 或非 cleanup service-not-ready 测试间接兜底。
- 保持 `tests/test_personal_wechat_text.py` 单独覆盖 personal WeChat cleanup service-not-ready observability，并锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查` 入口变体，避免这个渠道只对带任务引用的英文 cleanup 命令保留可观测性。
- 保持 personal WeChat cleanup 入口在文本成功回出后继续复用统一的 `[cleanup 私聊 smoke]` 日志协议，并至少带上 `date/channel/action/query/reply_head`，避免第二个接入渠道又长出 personal WeChat 专属日志格式。
- 保持 `tests/test_personal_wechat_text.py` 单独覆盖 personal WeChat 入口里的 `cleanup-shortcut` 这类 `chat-scoped task_ref -> jobs -> import correlation` 身份解析，避免这个私聊入口把 shortcut 当成普通字符串传下去却绕过 shared runtime 的 chat-scoped lookup。
- 保持 `tests/test_feishu_adapter.py` 单独覆盖 Feishu 私聊入口 cleanup service-not-ready observability，并锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查` 入口变体，避免这个渠道的私聊入站链路只能靠聚合 smoke 或英文带任务引用路径间接兜底。
- 保持 Feishu cleanup 入口在文本成功回出后继续复用统一的 `[cleanup 私聊 smoke]` 日志协议，并至少带上 `date/channel/action/query/reply_head`，避免第三个接入渠道又长出 Feishu 专属日志格式。
- 保持 `tests/test_feishu_adapter.py` 单独覆盖 Feishu 私聊入口 `cleanup-shortcut` 这类 `chat-scoped task_ref -> jobs -> import correlation` 身份解析，避免这个渠道把 `cleanup-shortcut` 当成普通字符串传下去却绕过 shared runtime 的 chat-scoped lookup。
- 保持 `tests/test_feishu_adapter.py -k "webhook_http_request and cleanup"` 单独覆盖 Feishu webhook cleanup 路由和 service-not-ready observability，并锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查` 入口变体，避免这个加密 webhook 入口只有正常路径回归、缺少未注入服务时的可观测性保护。
- 保持 `tests/test_wecom_adapter.py` 单独覆盖 WeCom 私聊入口 cleanup service-not-ready observability，并锁住 bare `cleanup` / bare `cleanup inspect` / `清理` / `清理检查` 入口变体，避免这个渠道的解密入站和加密回包路径只能靠聚合 smoke 或英文带任务引用路径间接兜底。
- 保持 WeCom cleanup 入口在文本成功回出后继续复用统一的 `[cleanup 私聊 smoke]` 日志协议，并至少带上 `date/channel/action/query/reply_head`，避免第四个接入渠道又长出 WeCom 专属日志格式。
- 保持 `tests/test_wecom_adapter.py` 单独覆盖 WeCom callback 里的 `cleanup-shortcut` 这类 `chat-scoped task_ref -> jobs -> import correlation` 身份解析，避免这个加密入站链路把 shortcut 当成普通字符串传下去却绕过 shared runtime 的 chat-scoped lookup。
- 保持 verification docs gate 继续显式校验 Telegram / personal WeChat / Feishu / WeCom 四个单渠道 `cleanup-shortcut` 门禁都还写在 `docs/NEXT_STEP.md` / `docs/STATUS.md`，避免前面几轮刚补上的 shared-runtime 身份链门禁从文档快照里漂走。
- 保持 `docs/STATUS.md` 里的 WeCom cleanup service-not-ready 快照和 Latest verification 同步到同一组跑数，避免同一轮结果在同一文件里写出两套数字。
- 保持 verification docs gate 继续显式校验 `success-event-append-failure observability` 命名观察，避免窗口台账把这类事件落盘失败可观测性写丢。
- 保持 verification docs gate 继续显式校验 `delete-failure observability` 命名观察，避免窗口台账把这类删除失败可观测性写丢。
- 保持 verification docs gate 继续显式校验 `correlation-missing unresolved-identity blank display` 命名观察，避免窗口台账把这条空白身份展示边界写丢。
- 保持 verification docs gate 继续显式校验 `correlation-missing inspect identity resolution` 命名观察，避免窗口台账把 chat-scoped inspect 身份解析成功后的文本边界写丢。
- 保持 verification docs gate 继续显式校验 `correlation-missing rejection guidance` 命名观察，避免窗口台账把这类关联缺失后的 follow-up 引导写丢。
- 保持 verification docs gate 继续显式校验 `post-cleanup cleanup inspect confirmation` 命名观察，避免窗口台账把 cleanup 成功后的复核文本边界写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref post-cleanup cleanup inspect confirmation` 命名观察，避免窗口台账把 chat-scoped cleanup 成功后的复核文本边界写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref target-missing cleanup inspect follow-up guidance` 命名观察，避免窗口台账把 chat-scoped target-missing inspect follow-up 写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref source-missing cleanup inspect follow-up guidance` 命名观察，避免窗口台账把 chat-scoped source-missing inspect follow-up 写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref source-type-unsupported cleanup inspect follow-up guidance` 命名观察，避免窗口台账把 chat-scoped source-type inspect follow-up 写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref guard-rejected cleanup inspect follow-up guidance` 命名观察，避免窗口台账把 chat-scoped guard-rejected inspect follow-up 写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref target-missing rejection guidance` 命名观察，避免窗口台账把 chat-scoped target-missing 阻断后的 follow-up 引导写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref source-missing rejection guidance` 命名观察，避免窗口台账把 chat-scoped source-missing 阻断后的 follow-up 引导写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref source-type-unsupported rejection guidance` 命名观察，避免窗口台账把 chat-scoped source-type 阻断后的 follow-up 引导写丢。
- 保持 verification docs gate 继续显式校验 `source-type-unsupported rejection guidance` 命名观察，避免窗口台账把这类 source-type 阻断后的 follow-up 引导写丢。
- 保持 verification docs gate 继续显式校验 `chat-scoped task_ref guard-rejected rejection guidance` 命名观察，避免窗口台账把这类 chat-scoped guard-rejected 阻断后的 follow-up 引导写丢。
- 保持 verification docs gate 继续显式校验 cleanup 窗口写成 `已完成` 后，`当前 cleanup 协议观察` 不再残留 `尚未到最早可结束日期`、`已到最早可结束日期` 或 `真实私聊 cleanup smoke` 待补文案，避免窗口已收口后台账还挂着进行中阻塞文本。
- 在 cleanup 验证窗口正式退出前，至少评估并记录 PT 下载任务的做种状态 guardrail（`pt_min_seed_hours` 保护、下载器 seeding 信息等）是否已在 guardrail 里覆盖；窗口台账里必须明确写出“当前 cleanup guardrail 未读取下载器 seeding 状态、`pt_min_seed_hours` 未进入 cleanup 阻断判断、因此本窗口只记录风险，不扩 cleanup 行为”。
- 保持 cleanup 身份展示边界稳定：只有 `chat-scoped task_ref` 真正从 `jobs` 解析出身份时才回显和记录 `task_id/task_hash`；普通 correlation-missing inspect 继续显示 `-`，cleanup follow-up 继续落到稳定的 hash / id。
- 保持 `chat-scoped task_ref` 在 `job_event` 关联查询失败时也继续打印 resolved `lookup_task_ref/task_id/task_hash`，且 inspect / cleanup 文本不要丢掉已解析出的身份。
- 保持 `chat-scoped task_ref` 命中历史 `import.succeeded` 但缺 `source_path/target_path` 时，也继续回显 resolved identity，并保持 correlation-missing 文本协议不变。
- 保持 `chat-scoped task_ref` 在真正执行 cleanup 但删除失败时，也继续使用已解析出的真实任务身份写 `cleanup.failed` 事件和红色日志。
- 保持 `chat-scoped task_ref` 在 cleanup 已成功但 `cleanup.succeeded` 事件写入失败时，也继续打印真实任务身份，且不隐藏成功文本。
- 保持 `chat-scoped task_ref` 在 guardrail 判成 `source_type_unsupported` 时，也继续用真实关联任务身份打印阻断日志和 follow-up。
- 保持 cleanup service 未注入时，`cleanup` / `cleanup inspect` 也继续打印红色中文 `[cleanup 服务未就绪]` 日志、`动作=cleanup/cleanup_inspect`、`查询=` 与 `[处理建议]` 修复提示，避免四渠道只回 `SERVICE_NOT_READY_TEXT` 却没有运维可见性。
- 保持 cleanup 失败可观测性稳定：
  - 删除失败日志：`[cleanup 执行失败] + event_type=cleanup.failed + task_ref + source + target`
  - 关联查询失败日志：`task_ref + lookup_task_ref/task_id/task_hash`
  - 事件写入失败日志：`task_ref + task_id/task_hash + source + target`
- 只允许修：
  - shared runtime 回归
  - 渠道适配胶水回归
  - 显式中文日志和修复提示缺口
- 保持 bring-up 入口稳定：
  - `.env.example`
  - `Makefile`
  - `Dockerfile`
  - `docker-compose.yml`
  - `docs/GETTING_STARTED.md`
- 保持 `make run` 在 `ENV_FILE` 缺失时先打印红色中文 `[环境文件缺失]` 日志和 `[处理建议]`，并支持 `ENV_FILE=/绝对路径 make run`，避免当前 Telegram bring-up 还没进入 runtime 就掉进 shell 原始报错。
- 保持 Telegram-only bring-up 在缺少 BT 下载器角色绑定时只打印 `[BT 订阅后台扫描未启动]` 警告、不把 `app.main` 卡死在启动前，避免最小私聊验证被非主线 BT 配置误拦截。
- 保持 `tests/test_telegram_bot.py` 继续单独锁住 `[BT 订阅后台扫描未启动]` + `[处理建议]` 这组日志，避免这条 bring-up warning 下一轮又悄悄退回成无提示状态。
- 保持 Telegram 启动在网络 / DNS 失败时也打印红色中文 `[Telegram 启动失败]` 和 `[处理建议]`，避免当前主线 bring-up 还停留在英文 traceback。
- 保持 `runtime_process snapshot` 继续如实反映“当前有没有运行中的 `app.main`”，docs gate 只要求 `docs/STATUS.md` 和窗口台账一致，不把它硬编码成固定停止态。

## Do not do

- 不新增自动 inspect、自动 cleanup、批量 cleanup、删种或新的 cleanup workflow。
- 不放宽现有 cleanup guardrail、删除范围或 correlation 校验。
- 不把四渠道适配重构成通用多渠道平台、通用 webhook 总线或通用 plugin / skill / MCP 平台。
- 不在这一步启动 `series / anime` 实现、shared private-chat 交付体验 polish、最小人类可用入口之外的新产品面、BT 共享评分器重写、Jellyfin / Plex 支持或其他新集成。
- 不回退现有文本协议：
  - `cleanup inspect <任务ID或Hash>` / `清理检查 <任务ID或Hash>`
  - `cleanup <任务ID或Hash>` / `清理 <任务ID或Hash>`
  - bare `cleanup` / `清理`
  - bare `cleanup inspect` / `清理检查`

## Done when

- 已完成 7 天验证窗口。
- 四个渠道各至少完成 1 次真实私聊 shared-runtime smoke。
- `tests/test_cleanup_cross_channel_smoke.py` 持续通过。
- cleanup discoverability / inspect / execution / rejection guidance / success follow-up / failure observability 没有协议回退。
- `docs/CLEANUP_VERIFICATION_WINDOW.md` 已完整记录窗口起止日期、证据、当前状态和当前结论。
- `docs/STATUS.md` 快照、`docs/NEXT_STEP.md` 目标和窗口台账保持一致。

## After this step

1. 独立后台下载完成轮询（当前已补上 `PostDownloadAutoImportService.run_once()` 的最小后台 tick，`download_monitor` 待完成列表已补齐限流读取，且独立 downloader status polling 最小闭环已接入应用启动/停止链；后续只继续收口这条链路的验证与可观测性，不扩成通用 scheduler 平台）。
2. `series / anime` 独立名称解析最小实现（结构化解析 + 小型识别词/替换配置，parser-first，不做 DSL）。
3. `.ass` 字幕支持评估与最小实现（与 `series / anime` 同步收口）。
4. `shared private-chat runtime` 最小抽离：把 `handle_private_chat_query_text` 从 `app/bot/telegram_bot.py` 抽到独立 shared runtime 模块，改成显式 runtime context / injected capability；保留 `微信登录` 的 Telegram 二维码回传能力为注入项，不做多渠道平台化。
5. shared private-chat 交付体验收口（图片 / 信息卡片 / 字符排版 / 状态信息清晰化，不做 Web UI）。
6. 最小人类可用入口继续补齐（quick start / 配置模板 / 首个渠道 10 分钟跑通）。
7. BT 共享确定性评分器。
8. Jellyfin / Plex 支持（后续）。
9. plugin 体系继续后置。
