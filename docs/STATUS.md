# Current status (v446)

## Current mainline

- **质量硬化** 与 **保守版收尾发布准备** 都已收工；当前主线已正式切到 **搜索相关性优化**。
- 当前这一轮已继续补齐标题噪音抑制：`Chapter 4 / Part 2 / 空格数字续作 + Extended / IMAX / Special Edition / Final Cut / Director's Cut / Ultimate Edition + 年份` 这类输入现在不会再把 sequel/chapter 数字吞掉。
- 首版发布矩阵已冻结为：Telegram 私聊 + PT Transmission + Emby + movie-first 主链。
- 三座大山保持完成态：`app/services/add_to_downloader.py` `574` 行 / `app/services/import_to_library.py` `585` 行 / `app/services/search_media.py` `460` 行。

## Current health

- 仓库级质量入口保持可用：`make quality`、`make verify-mainline`、`make verify-quality-gates` 当前都可复验。
- movie-first 搜索相关性本轮继续收口：TMDB 低置信命中不再抢主导权；BT fallback 排序已覆盖单条候选、少量噪音候选、续作数字与括号年份这几类真实输入。
- 续作别名对齐现在继续前推一格：`沙丘第二部 2024`、`Dune II 2024`、`Mission Impossible 7 2023` 这类输入不再把续作信息吞掉，TMDB 与搜索 query 会更稳定命中真正的 sequel。
- `Dune Part 2 2024`、`John Wick IV 2023` 这类“数字 part / roman chapter”别名现在也会更稳定对齐 `Part Two` / `Chapter 4`，不再因为 token 形式不同就降级成低置信 TMDB 命中。
- `John Wick Chapter Four 2023` 这类“章节词 + 英文数字词”现在也会稳定对齐 `Chapter 4`，不再因为 `Four` 没被归一而走低置信回退。
- `Fast Ten 2023` 这类“标题尾部英文数字词”现在也会稳定对齐 `Fast X`，不再因为 `Ten` 与 `X` 形式不同而错过高置信 TMDB 命中。
- sequel-digit 搜索解析现已同时覆盖半角与全角括号年份：`沙丘 2 (2024)` 与 `沙丘 2（2024）` 当前都会保住续作数字，不再回退成缺失 `2` 的搜索标题。
- `John Wick Chapter 4 Extended 2023`、`Dune Part 2 Extended 2024`、`Mission Impossible 7 IMAX 2023`、`Fast X Special Edition 2023` 这类“续作/章节 token + 版本噪音词 + 年份”输入现在会先剥掉尾部噪音词，再保住真正的 sequel/chapter token，不再把 `4 / 2 / 7 / X` 吞掉。
- `Blade Runner Final Cut 1982`、`Alien Director's Cut 1979`、`Batman v Superman Ultimate Edition 2016` 这类“电影标题 + 版本 cut/edition 词 + 年份”输入现在也会先剥掉尾部版本词，再把搜索标题对齐回真正片名；但 `The Final Cut 2004` 这类本体标题不会被误删空。
- 当前 `.env` / `.env.example` / `docs/TEST_ENV.md` 里的 `DOWNLOADER_INSTANCES` 示例已改成 shell-safe 写法；直接用 `set -a && . ./.env && set +a` 时不会再因为分号值把后半段当成命令执行。
- 当前 live smoke 真相仍分两段：
  - `search -> select -> confirm -> status` 已在真实 Prowlarr / PT Transmission 上跑通。
  - `status -> import -> confirm -> refresh` 已在真实 PT Transmission / Emby 上跑通。
- 当前环境真相（`2026-04-24` 本机 probe）：
  - `19091` PT Transmission RPC 与 `18096` Emby API 当前可达；`18098/api/v2/torrents/info` 当前返回 `200 OK`。
  - `19092` BT Transmission 当前 `ss -ltnp` 仍能看到监听，但本轮 `curl -si http://127.0.0.1:19092/transmission/rpc` 连续两次退出码 `7`；不要把它写成“当前已复验 RPC 可达”。
  - `/data/downloads/tr`、`/data/downloads/tr-bt`、`/data/downloads/qb` 与 `/data/library/movies` 当前 `stat -c "%d %n"` 设备号都为 `2096`；硬链接前提仍满足。

## Latest verification

- `make quality`：通过；docs/tests 阶段 `27 passed`
- `make verify-mainline`：通过
- `make verify-quality-gates`：通过
- `make test`：`1761 passed, 2 skipped`
- 搜索相关回归：`.venv/bin/python -m pytest -q tests/test_search_media.py` 为 `137 passed`
- 搜索 + TMDB focused：`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_tmdb_client.py` 为 `147 passed`
- downloader focused：`.venv/bin/python -m pytest -q tests/test_add_execution_follow_up.py tests/test_add_to_downloader.py tests/test_private_chat_confirm_runtime.py` 为 `119 passed`
- import focused：`.venv/bin/python -m pytest -q tests/test_import_pending_write_through_state.py tests/test_import_to_library.py -k "import_by_task_ref or record_pending_approval or pending_state_unavailable or copy_fallback_pending"` 为 `48 passed, 100 deselected`
- 当前本机探针：
  - `curl -si http://127.0.0.1:19091/transmission/rpc` 返回 `409 + X-Transmission-Session-Id`
  - `curl -s http://127.0.0.1:18096/System/Info/Public` 返回 `ServerName`
  - `curl -si http://127.0.0.1:18098/api/v2/torrents/info` 返回 `200 OK`
  - `curl -si http://127.0.0.1:19092/transmission/rpc` 连续两次退出码 `7`；但 `ss -ltnp | rg ":19091|:19092|:18096|:18098"` 仍显示 `19092` 在监听
- 已保存的真实 smoke 证据：
  - 当前仓库未保留 `tmp_tests/verify_release_*.py` 源脚本；不要把已清理的临时脚本路径继续写成现成验证入口。
  - 前半段真实任务：`task_id=17` / `task_hash=1ea022ed0c3cbe9139469a8a58f5bfcfaa1875de`；已保存证据显示可再次进入 `status -> 临时 SQLite download_monitor 落盘`。
  - 后半段真实任务：`task_ref=d8f737c1468646c8ab35279fa10f89f89e88428e`；已保存证据显示可再次进入 `import_by_task_ref -> pending approval -> import.succeeded -> refresh.succeeded`。
  - 后半段真实目标：`/data/library/movies/抓住它 Catch It (2015)/Catch.It.2015.1080p.WEB-DL.H264.AAC-PTerWEB.mp4`
  - metadata 现象：`Catch It 2015` 仍会命中 `TMDB 未命中 title=抓住它, year=2015`，但不回滚 `import.succeeded` 或 `refresh.succeeded`

## Current biggest risk

- 当前最大治理风险仍是文档漂移：不要再把“代码里已实现”写成“首版承诺”。
- 当前机器环境真相要继续按当轮探针写，不要把 `19092` 的旧“可达”或更早的旧“不可达”结论直接抄回入口文档。
- 当前最大发布前不确定性已收缩到搜索相关性偏好，而不是协议或环境主链失败；当前更像“别名与排序继续打磨”，不是“主链没通”。
- 运行时编排层仍较依赖 `bot_data` 字符串 key 和跨模块常量约定；这比三座大山行数更值得警惕。

## Recommended Next Operator Command

```text
保守版发布准备已可宣告完成；如需继续，优先做搜索相关性优化，不必再把 19092 / 18098 当当前 blocker。
```
