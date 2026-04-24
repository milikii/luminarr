# Current status (v452)

## Current mainline

- **质量硬化** 与 **保守版收尾发布准备** 都已收工；当前主线已正式切到 **搜索相关性优化**。
- 当前这一轮刚完成：movie-first 的 BT 排序器与 fallback query 现在也会复用共享标题归一；`Dune Part 2 -> Dune Part Two` 这类 sequel alias 不再在无 TMDB 改写路径里被误判成 `title_mismatch`，`流浪地球2` 这类 fallback query 也不会再把 `II` / `5.1` 之类噪音拼回公共标题。
- 更早完成的 `query 解析职责拆分` 继续保持完成态：`ParsedMovieQuery` / `parse_movie_query()` 不再挂在 `search_request_context.py` 下面。
- 首版发布矩阵已冻结为：Telegram 私聊 + PT Transmission + Emby + movie-first 主链。
- 三座大山保持完成态：`add_to_downloader.py` `574` 行 / `import_to_library.py` `585` 行 / `app/services/search_media.py` `568` 行。

## Current health

- 仓库级质量入口保持可用：`make quality`、`make verify-mainline`、`make verify-quality-gates` 当前都可复验。
- 搜索链当前已稳定覆盖三类核心相关性问题：续作/章节别名归一、尾部版本噪音剥离、TMDB 高置信长标题命中；当前默认优先顺序仍是 `TMDB 英文标题 -> original_title -> 用户标题`。
- movie-first 前台结果当前会继续过滤剧集形态假阳性、明显 outlier、`Extras / making of / bonus` 这类附加内容，并在展示前去重同标题与 `2 / II` 这类近似重复标题。
- 当前这一轮新增：BT 排序器与 fallback query 也已接入共享标题归一；`Dune Part 2 2024` 命中 `Dune: Part Two ...` 的无 TMDB 改写路径不会再直接掉成“未找到候选”，`流浪地球2` 的 fallback query 也不会再把 `II / hd / 5.1` 拼成伪标题。
- 搜索链结构继续收口：query parser、标题噪音规则、TMDB 高置信判断、等价 query 去重、BT 排序器和 fallback token 现在都围绕共享标题归一层实现，后续补规则不需要再分散改两三套逻辑。
- 当前 live smoke 真相仍分两段：`search -> select -> confirm -> status` 已在真实 Prowlarr / PT Transmission 跑通；`status -> import -> confirm -> refresh` 已在真实 PT Transmission / Emby 跑通。
- 当前环境真相（`2026-04-24` 本机 probe）：`19091` PT Transmission、`18096` Emby、`18098` qBittorrent API 可达；`19092` 端口仍在监听，但 `curl -si http://127.0.0.1:19092/transmission/rpc` 连续两次退出码 `7`，不要写成“已复验 RPC 可达”；下载与媒体目录设备号当前一致，硬链接前提仍满足。

## Latest verification

- `make quality`：通过；docs/tests 阶段 `28 passed`
- `make verify-mainline`：通过
- `make verify-quality-gates`：通过
- `make test`：`1761 passed, 2 skipped`
- 搜索 focused：`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_bt_candidate_scorer.py` 为 `192 passed`
- 搜索 + TMDB focused：`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_tmdb_client.py` 为 `175 passed`
- downloader focused：`.venv/bin/python -m pytest -q tests/test_add_execution_follow_up.py tests/test_add_to_downloader.py tests/test_private_chat_confirm_runtime.py` 为 `119 passed`
- import focused：`.venv/bin/python -m pytest -q tests/test_import_pending_write_through_state.py tests/test_import_to_library.py -k "import_by_task_ref or record_pending_approval or pending_state_unavailable or copy_fallback_pending"` 为 `48 passed, 100 deselected`
- 当前真实 smoke 证据仍有效：前半段 `task_id=17` / `task_hash=1ea022ed0c3cbe9139469a8a58f5bfcfaa1875de` 可再次进入 `status`；后半段 `task_ref=d8f737c1468646c8ab35279fa10f89f89e88428e` 可再次进入 `import_by_task_ref -> pending approval -> import.succeeded -> refresh.succeeded`。当前仓库未保留 `tmp_tests/verify_release_*.py` 源脚本，不要再把它们写成现成入口。

## Current biggest risk

- 当前最大治理风险仍是文档漂移：不要再把“代码里已实现”写成“首版承诺”。
- 当前机器环境真相要继续按当轮探针写，不要把 `19092` 的旧“可达”或更早的旧“不可达”结论直接抄回入口文档。
- 当前最大发布前不确定性已收缩到搜索相关性偏好，而不是协议或环境主链失败；当前更像“别名与排序继续打磨”，不是“主链没通”。
- 运行时编排层仍较依赖 `bot_data` 字符串 key 和跨模块常量约定；这比三座大山行数更值得警惕。

## Recommended Next Operator Command

默认继续施工时，直接复制下面这句给 AI：

```text
按 AGENTS.md + docs/OPERATOR_RUNBOOK.md 的“默认 3 轮施工”执行。
```
