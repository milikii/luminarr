# docs/BT_BATCH_PLAN.md (v1)

> 目的：把 `docs/NEXT_STEP.md` 里新提升的 **BT 批量任务最小预览** 主线先设计成一个能马上施工、又不碰下载确认真相边界的最小蓝图。
>
> 本文件是**蓝图**，不是台账。落地后的详细闭环继续收口到后续主线台账；当前先不给 `STATUS.md` 回灌长记录。
>
> 上游决策：`docs/DECISIONS.md` D-015 / D-017 / D-038。

## 1. 为什么先做这条，而不是 Jellyfin / Plex 真实联调

- 当前本地正式真实联调栈明确写到 `Transmission + Emby`；`docs/TEST_ENV.md` 还没有 Jellyfin / Plex 的固定测试栈入口。
- BT 侧已经有长期边界 `D-038`，但还缺一个当前可施工的最小闭环。
- 所以这次 promoted 主线先选 **BT 批量任务**，并且先只做 **确定性批量预览**，不在第一步碰批量 dispatch。

## 2. 要解决的真实问题

当前 BT 路径里其实有两块能力：

1. `bt搜 <关键词>` / `bt search <关键词>` 可以做只读探索，给用户回一个候选列表；
2. `pure_bt` 下载链会直接从候选里挑一个“最优单片”进入现有下载确认链。

缺的正好是中间这块：

- 用户想一次看多条 BT 候选的**批量预览**；
- 用户想按**编号范围**收口一个批量集合；
- 但当前系统没有一个明确的、可复用的结构来承接这类“先预览、后确认”的 BT 批量请求。

## 3. 当前主线只做什么

当前 promoted 主线先只做下面这一条最小闭环：

1. 用户发送 BT 批量预览请求；
2. parser / routing 把它解析成结构化批量预览请求；
3. 确定性代码调用现有 BT source adapter / raw search；
4. 确定性代码完成去重、范围过滤、数量截断；
5. 系统回 **批量预览文本**，明确这一步仍是只读，不会 dispatch 下载器。

这一步**不做**批量 `confirm`、不创建批量 approval、也不自动投递下载器。

## 4. 最小输入协议

当前先支持两种前缀：

- `bt批量 <关键词>`
- `bt batch <关键词>`

第一阶段的最小范围语法：

- `bt批量 <关键词> 1-3`
- `bt batch <关键词> 2,4,6`

约束：

- 范围只作用在“已搜到的候选列表编号”，不让 LLM 自由理解；
- 如果范围缺失，就默认预览前 `5` 条；
- 如果范围非法、为空或越界，就显式回中文拒绝文本。

## 5. 预览输出长什么样

批量预览文本至少要包含：

- 原始查询
- 实际命中的编号范围
- 每条候选的标题 / 来源站点 / 做种数 / 大小 / 链接参考
- 一句明确只读提示
- 下一步提示：后续批量确认会单独作为下一阶段，不在这一步执行

## 6. Phase 顺序

- **Phase 1**：新建批量预览请求 parser 和候选过滤 helper；只处理关键词 + 编号范围。
- **Phase 2**：把 shared runtime / Telegram BT 入口接到批量预览路径，复用现有 `search_raw_candidates()`。
- **Phase 3**：补 focused tests，确认无结果、范围非法、范围越界、去重后列表为空这些 fail-closed 路径都回中文文本。

## 7. 可测量退出条件

当前主线视为 **已收口**，满足以下任一条即可：

1. `bt批量` / `bt batch` 已能回确定性批量预览文本，且 `.venv/bin/python -m pytest -q tests/test_pure_bt.py tests/test_search_media.py tests/test_telegram_bot.py -k "bt_batch or bt_read_only_helper"` 全绿；
2. 或本轮代码改动 `< 20` 行、只是为同一个 batch parser 再补一条 `if/elif/log` 诊断分支，触发 `AGENTS.md §11` 停机规则。

## 8. 不做清单

- 不做 BT 批量自动下载
- 不做批量 approval / 批量 `confirm`
- 不把这一步扩成 Jellyfin / Plex 真实联调
- 不接未知站点、动态站点、CAPTCHA 或登录态站点
- 不让 LLM 决定抓哪一页、选哪几条、是否直接投递
