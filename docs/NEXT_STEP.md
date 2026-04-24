# Next step (v344)

## Current goal

- **质量硬化** 与 **保守版收尾发布准备** 都已完成；当前默认分支若继续推进，唯一主线就是 **搜索相关性优化**。
- 这条主线不再碰发布矩阵、真实 smoke 范围或副作用边界，只在现有 movie-first 搜索链里继续收敛“用户输入什么，前几条候选能不能更像他要的那一部”。
- 当前刚完成的一条最小闭环是：**query 解析职责拆分 · 第 1 轮**。
- 当前批次已通过本机复验确认：`make quality` 绿灯；`.venv/bin/python -m pytest -q tests/test_search_media.py` 为 `156 passed`；`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_tmdb_client.py` 为 `173 passed`。
- 当前这一轮已经补齐：
  - `John Wick Chapter 4 Extended 2023` 这类“章节数字 + 版本噪音词 + 年份”输入现在不会再把 `4` 吞掉，TMDB 与搜索 query 会继续稳定落到 `Chapter 4`
  - `Dune Part 2 Extended 2024` 这类“part 数字 + 版本噪音词 + 年份”输入现在不会再把 `2` 吞掉，query 解析会继续保住 sequel token
  - `Mission Impossible 7 IMAX 2023` 这类“空格数字续作 + IMAX + 年份”输入现在不会再把尾部数字吞回基片标题
  - `Fast X Special Edition 2023` 这类“尾部 sequel token + 版本噪音词 + 年份”输入现在会先剥掉 `Special Edition`，再稳定保住 `Fast X`
  - `Blade Runner Final Cut 1982`、`Alien Director's Cut 1979`、`Batman v Superman Ultimate Edition 2016` 这类“电影标题 + cut/edition 词 + 年份”输入现在会把尾部版本词剥掉，再把 TMDB 与搜索 query 对齐回真正片名
  - `Blade Runner The Final Cut 1982`、`Alien The Director's Cut 1979` 这类带前置冠词的尾部版本短语现在也会整段剥掉，不再把标题错误残留成 `Blade Runner The` / `Alien The`
  - `Dune Part 2 IMAX Enhanced 2024`、`Avatar Extended Cut 2009`、`Batman v Superman Special Extended Edition 2016`、`Blade Runner Theatrical Version 1982`、`Aliens Collector Edition 1986` 这类常见复合版本词写法现在也会回到真实片名，不再把 sequel token 吞成 `Part Enhanced`，或把 `Extended Cut / Theatrical Version / Collector Edition` 残留进搜索标题
  - `Batman v Superman 2016` 这类“主标题 + 官方多词副标题”的输入现在会把 `Batman v Superman: Dawn of Justice` 视为高置信 TMDB 命中，优先直接用官方长片名去搜；但 `John Wick 2023 -> John Wick: Chapter 4` 这类续作后缀不会被误判成同片高置信
  - `The Final Cut 2004` 这类本体标题现在不会被错误地整段剥成空标题或只剩冠词
  - 当前标题噪音剥离规则已经抽到共享归一层；query 解析和 TMDB 候选比对复用同一套 `Extended / Final Cut / Director's Cut / Ultimate Edition` 规则，不再继续在两个模块里各写一份
  - 当前共享标题噪音词表也已改成声明式词表 + 统一正则拼装；后续若继续补版本词，默认只改共享词表，不再直接手改整段大正则
  - `Alien Remastered 1979`、`Dune Part 2 Theatrical 2024`、`Batman v Superman Uncut 2016`、`John Wick Chapter 4 Remastered 2023` 这类输入现在也会复用同一套共享尾部噪音词规则，不再继续把 `Remastered / Theatrical / Uncut` 留在搜索标题里
  - `Dune Part 2 Unrated 2024`、`Blade Runner Anniversary Edition 1982`、`Avatar Collectors Edition 2009` 这类输入现在也会复用同一套共享尾部噪音词规则，不再继续把 `Unrated / Anniversary Edition / Collectors Edition` 留在搜索标题里
  - 当前 query 标题里的续作/章节 token 恢复逻辑也已收回共享标题归一层；`search_request_context.py` 不再单独维护那段正则和 match-key 比对细节
  - 当前 `search_media.py` 与 `search_reply_formatter.py` 也已直接依赖共享标题归一层；后续如果还要复用 `normalize_spaces`，不需要再通过 `search_request_context.py` 间接转手
  - 当前 `ParsedMovieQuery` 与 `parse_movie_query()` 已抽到独立 parser 模块；`search_request_context.py` 只保留请求编排职责，不再同时承担纯 query 解析
- 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态：`app/bot/private_chat_runtime.py` 当前 `468` 行，`app/bot/telegram_bot.py` 当前 `256` 行，不回退。
- 当前剩余空间仍是“继续打磨命中偏好”，不是“主协议还没通”；movie-first 主链、发布矩阵和质量入口继续保持完成态。

## User value

- 用户现在输入带 `Extended / IMAX / Special Edition / Final Cut / Director's Cut / Ultimate Edition` 这类版本噪音词的片名时，更不容易因为尾部脏词把真正的 sequel/chapter token 吞掉，或者把片名误留在版本 cut/edition 词上。
- 当前这套规则也已覆盖 `The Final Cut / The Director's Cut` 这类资源站常见写法；尾部前置冠词会和版本短语一起剥掉，不再把错误的 `The` 残留进搜索标题。
- 当前也已补到几类常见复合变体：`IMAX Enhanced`、`Extended Cut`、`Special Extended Edition`、`Theatrical Version`、`Collector Edition`；后续补版本词时，优先先判断是否只是同一类尾部噪音变体。
- 当前这一轮也顺手降低了后续维护成本：再加新一类尾部标题噪音词时，不需要同时改 query 解析和 TMDB 标题比对两套逻辑。
- 当前这一轮也补了一点结构降本：共享标题噪音规则不再靠一整段越滚越长的手写正则硬撑，后续新增变体时更容易做小改动和小回归。
- 当前这一轮也把 TMDB 置信判断补细了一点：官方长片名副标题可以直接走高置信命中，但会显式排除 `Part / Chapter / 2049` 这类更像续作的后缀，避免把基片误判成 sequel。
- 共享层现在已经继续覆盖 `Remastered / Theatrical / Uncut`；后续若还要补新一类版本词，默认优先走共享归一层，不再回到局部正则散改。
- 共享层现在也已经覆盖 `Unrated / Anniversary Edition / Collectors Edition`；后续若继续补版本词，优先判断是否仍属于尾部标题噪音，再统一并入共享层。
- 当前这一轮也继续降低了结构维护成本：若后面还要补 sequel/chapter 恢复规则，默认先改共享标题归一层，不再让 `search_request_context.py` 再长出第二套恢复实现。
- 当前这一轮也继续降低了模块耦合：搜索链里凡是纯标题归一工具，默认直接从共享标题归一层取，不再挂靠到 request context 模块。
- 当前这一轮也把模块边界再切清了一步：后续若继续补 query 解析规则，优先改 parser 模块和共享标题归一层，不再把 parser 逻辑混回 request context。
- 当前这条主线的价值也更直接：不改协议、不扩能力，只提高“搜索第一屏更像用户真正要的片”这件事。
- 后续若继续，仍然优先做这类 query 命中质量与排序偏好，不回头重开发布准备或结构瘦身。

## Only do

- 只在现有搜索链里做确定性相关性优化：
  - query 解析
  - TMDB 候选选择与置信判断
  - 既有 BT 排序器在 movie-first 搜索里的排序偏好
- 若默认分支重新出现红灯，只做首版承诺范围内最小修复。

## Do not do

- 不改发布矩阵，不重开真实 smoke 范围，不顺手把环境探针再写成产品承诺。
- 不新增用户可感知功能，不扩协议，不改 approval / jobs / lease / downloader / import 副作用边界。
- 不把搜索相关性问题混写成“Transmission / Emby 环境失败”或“搜索协议没通”；当前主问题是 query 命中质量与排序偏好。
- 不回到 `add_to_downloader.py`、`import_to_library.py`、`search_media.py` 为了数字再拆 thin wrapper。
- 不顺手把 BT / watchlist / 群聊 / UI 再开新支线。

## Done when

当前 **搜索相关性优化** 主线继续推进时，每一条最小闭环都应满足：

1. 改动只落在现有搜索链，不扩协议或副作用边界。
2. 搜索相关 focused tests 当前可通过，且 `make quality` 不回退。
3. `docs/STATUS.md` 与本文件能把“本轮到底修了哪类 query 命中问题”写成当前真相。
4. 当前默认分支质量入口不回退。

## After this step

1. 继续按最小闭环推进搜索相关性优化，例如别名归一、标题噪音抑制、同片不同版本偏好。
2. 如果默认分支出现红灯，再临时切回首版承诺范围内的最小修复。
