# Next step (v332)

## Current goal

- **质量硬化** 阶段已正式收工；当前进入新的 **收尾发布准备** 阶段。
- 这阶段不再继续追“把大文件再拆薄一点”或“再补一个新能力”，而是把已经基本完成的默认分支收成一个**可宣告首版发布准备完成**的状态。
- 当前刚完成的 promoted 主线是：**发布前 live smoke / 第 3 轮 + 发布前质量 gate / 第 4 轮**。
- 当前批次已通过本机复验确认：`make quality` 绿灯，`make verify-mainline` 绿灯，`make verify-quality-gates` 也已复验通过；其中 `make test` 为 `1748 passed, 2 skipped`。
- 当前批次已通过本机复验确认：`make quality` 已从“只跑 compile + docs/tests”升级成 **`compile + pyflakes + docs/tests`** 的最小静态 gate，且当前仓库可通过。
- 当前批次已通过本机复验确认：共享 BT 打分规则新增 `source_site_preferred` 后暴露的 4 条回归已修复；旧构造器兼容保持恢复，release group 也不再污染标题相关性排序。
- 当前批次已通过本机复验确认：Feishu / WeCom 本地真实 HTTP webhook tests 可在当前环境通过，不再成立“`verify-quality-gates` 固定卡在 webhook 监听权限限制”这条旧结论。
- 截至 `2026-04-23` 本轮本机复验，`19091 Transmission` 返回 `409 + X-Transmission-Session-Id`、`18096 Emby` 返回 `ServerName`、`18098/api/v2/torrents/info` 返回 `200 OK`；`19092` 端口监听仍在，但 `curl -si http://127.0.0.1:19092/transmission/rpc` 本轮连续两次退出码 `7`。因此当前不能再把 `19092` 写成“已复验 RPC 可达”，但这也不构成首版发布 blocker；其中 qB 测试栈仍要求 `WEBUI_PORT=18098` 与 `18098:18098` 同步映射。
- 当前保守首版发布矩阵已正式冻结：
  - 纳入首版承诺：Telegram 私聊、PT Transmission、Emby、movie-first 主链
  - 已实现但当前不纳入首版保证：personal WeChat / Feishu / WeCom、BT Transmission / qBittorrent、Jellyfin / Plex、BT 订阅等路径
- 当前 live smoke 已拿到一条真实后半段证据：`status d8f737c1468646c8ab35279fa10f89f89e88428e -> import -> confirm -> refresh` 在 PT Transmission / Emby 上成功，目标路径落到 `/data/library/movies/抓住它 Catch It (2015)/...`
- 当前 live smoke 也已拿到前半段真实证据：`沙丘 2021 -> select 1 -> confirm 1 -> status 1ea022ed0c3cbe9139469a8a58f5bfcfaa1875de` 已在真实 Prowlarr / PT Transmission 上成功跑通
- 当前前半段主链剩下的不是协议阻塞，而是搜索相关性持续优化空间：`沙丘 2021` 现在已能稳定命中 Dune 相关候选，并把 `Dune 2021` 顶到前列；后续若继续，只做更细偏好排序
- 当前 metadata 不是主 blocker：`Catch It 2015` 导入后命中 `metadata.failed(TMDB 未命中 title=抓住它, year=2015)`，但不回滚 `import.succeeded + refresh.succeeded`
- 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态：`app/bot/private_chat_runtime.py` 当前 `468` 行，`telegram_bot.py` 当前 `256` 行，不回退。

## User value

- 当前保守版发布准备主线已经收死：文档真相、发布矩阵、真实前后半段 smoke、发布前最小静态 gate 都已落地。
- 当前文档口径也已重新收口成两条线：首版发布承诺矩阵单独写，当前机器环境探针真相单独写，避免把环境波动误当成产品承诺。
- 当前更有用户价值的下一步不再是继续打磨默认分支，而是视用户价值决定是否继续做**搜索相关性优化**，例如继续收敛国外 PT 站上的标题命中精度或偏好不同分辨率/体积区间。

## Only do

- 当前默认分支内不再继续追新的发布准备改动。
- 只允许做两类后续动作：
  - 若要继续，就做搜索相关性优化，不改发布矩阵和副作用边界
  - 若默认分支重新出现红灯，再做首版承诺范围内的最小修复

## Do not do

- 不回到 `add_to_downloader.py`、`import_to_library.py`、`search_media.py` 继续为了数字硬拆 thin wrapper。
- 不新增用户可感知功能，不扩协议，不顺手把 BT / watchlist / 群聊 / UI 再开新支线。
- 不把“代码里有实现”直接等同于“首版发布承诺”；未冻结进发布矩阵的能力，只能当作已实现但当前不纳入发布保证。
- 不继续沿用“Feishu / WeCom webhook smoke 在当前环境固定失败”这条旧结论；除非后续复验再次失败，否则不得再把它写回当前主线真相。
- 不把 BT Transmission / qBittorrent / Jellyfin / Plex 的当前环境状态，自动升级成首版发布承诺。
- 不把 `19092` 的旧“可达”或更早的旧“不可达”结论直接写回当前真相；当前环境状态必须以当轮探针为准。
- 不把 `18098` 当前可达自动升级成首版发布承诺。
- 不为了追 live smoke 顺手把验证范围扩成四渠道、BT 或所有下载器 provider 全覆盖。
- 不把当前“搜索相关性偏差”混写成“Transmission / Emby 环境失败”或“搜索协议没通”；协议链已经打通，问题只剩 query 命中质量。
- 不在当前保守版发布准备已完成后，重新把主线拉回“继续瘦身大文件”或“顺手扩功能”。

## Done when

当前 **发布前质量 gate / 第 4 轮** 视为 **完成**，需要同时满足：

1. `make quality` 已包含最小静态 gate，且当前仓库可通过。
2. `make verify-mainline` 与 `make verify-quality-gates` 当前都可通过。
3. `docs/STATUS.md` 与本文件已把质量 gate、真实 smoke 和后续只剩“搜索相关性”这件事写成统一真相。
4. 当前 docs / quality gate 不回退。

## After this step

1. 当前保守版发布准备可宣告完成。
2. 若继续推进，优先做搜索相关性优化；BT / qB 不属于这一轮首版 blocker，但环境真相仍要按当轮探针单独记录。
