# Next step (v335)

## Current goal

- **质量硬化** 与 **保守版收尾发布准备** 都已完成；当前默认分支若继续推进，唯一主线就是 **搜索相关性优化**。
- 这条主线不再碰发布矩阵、真实 smoke 范围或副作用边界，只在现有 movie-first 搜索链里继续收敛“用户输入什么，前几条候选能不能更像他要的那一部”。
- 当前刚完成的一条最小闭环是：**续作 / 章节别名对齐 · 第 3 轮**。
- 当前批次已通过本机复验确认：`make quality` 绿灯；`.venv/bin/python -m pytest -q tests/test_search_media.py` 为 `126 passed`；`.venv/bin/python -m pytest -q tests/test_search_media.py tests/test_tmdb_client.py` 为 `135 passed`。
- 当前这一轮已经补齐：
  - `Part Two / II / 第二部` 这类续作别名现在会在 TMDB 置信匹配里更稳定对齐，不再轻易把 sequel 误当成基片或邻近片名
  - `Mission Impossible 7 2023` 这类“英文标题 + 空格数字续作”现在不会再把空格数字吞成 `Impossible7`
  - `沙丘第二部 2024`、`Dune II 2024`、`沙丘 2（2024）` 这几类 query 现在都能更稳定落到同一部 sequel
  - `Dune Part 2 2024`、`John Wick IV 2023` 这类“数字 part / roman chapter”别名现在也能稳定对齐 `Part Two` / `Chapter 4`
  - `John Wick Chapter Four 2023` 这类“章节词 + 英文数字词”现在也能稳定对齐 `Chapter 4`
- 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态：`app/bot/private_chat_runtime.py` 当前 `468` 行，`app/bot/telegram_bot.py` 当前 `256` 行，不回退。
- 当前剩余空间仍是“继续打磨命中偏好”，不是“主协议还没通”；movie-first 主链、发布矩阵和质量入口继续保持完成态。

## User value

- 用户现在输入续作别名时，更不容易被错误 query 拖到基片、邻近片或丢掉 sequel token。
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
