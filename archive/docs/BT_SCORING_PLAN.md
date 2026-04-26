# docs/BT_SCORING_PLAN.md (v1)

> 目的：把 `docs/NEXT_STEP.md` 的 `After this step` "BT 共享确定性评分器" 主线提前设计到位，Codex 按文档施工。
>
> 本文件是**蓝图**，落地后的详细闭环继续走 `docs/BT_SCORING_LOG.md`（Codex 按主线启动时自建）。
>
> 上游决策：`docs/DECISIONS.md` D-021 / D-022 / D-030。

## 1. 要解决的真实问题

当前三条 BT 路径各自有一套简化的选源逻辑：

- `pure_bt` 文本查询：`app/services/pure_bt.py` 的最小单片优选
- `btsub` 订阅扫描：`app/services/manage_bt_subscription.py` 的 `_scan_chat_once` 选源
- 媒体型 BT（`movie/series/anime`）走 Prowlarr 主链的候选展示

这三条规则都在项目内部、都是确定性代码，但没共用。**当前主线的目标是把三条的"面对多候选挑一个"收敛成同一个 helper**，不引入 DSL、不引入 LLM、权重显式。

## 2. 输入：统一候选字段

评分器接收的候选必须先被**共享 BT 来源适配层**归一化成：

```python
@dataclass(frozen=True, slots=True)
class BTCandidate:
    source_site: str             # 来源站点名（Prowlarr indexer id / WebSource rule name）
    title: str                   # 原始标题
    magnet_or_torrent_url: str   # 下载链接
    size_bytes: int | None
    seeders: int | None
    leechers: int | None
    resolution: str | None       # 1080p / 2160p / 720p / None
    codec: str | None            # x264 / x265 / HEVC / None
    source_type: str | None      # WEB-DL / BluRay / BDRip / WEBRip / Remux / None
    audio: tuple[str, ...]       # 2.0 / 5.1 / Atmos 等
    release_group: str | None
    age_days: int | None         # 发布距今天数
    media_kind: str              # "movie" | "series" | "anime" | "raw_bt"
```

来源适配层的归一化结果必须统一（对 `Prowlarr` / `WebSource` 都一样）；归一化本身不属于评分器范围。

## 3. 预过滤（零权重，直接淘汰）

评分前先跑预过滤，任一不通过就 drop 候选：

| 过滤项 | 规则 |
|---|---|
| 链接 | `magnet_or_torrent_url` 非空且看起来合法 |
| 标题命中 | 需求 title 的主词至少 80% 字符出现在候选 title 里（按需求方分词） |
| 去重 | 相同 `magnet infohash` 已见过 → drop |
| 低质量黑名单 | 标题含 `摄像` / `枪版` / `TS` / `CAM` / `TC` 等标记 → drop |
| 合集 / 整季（pure BT 单片模式下） | 标题含 `合集` / `全集` / `S01-S03` 等 → drop |

预过滤清单可配置文件：`app/services/bt_scoring_rules.yml`（YAML）；不存在时走内置最小集。

## 4. 评分信号和权重

每个信号输出 0.0–1.0 分，乘权重求和。**显式权重，不 DSL**：

```yaml
# app/services/bt_scoring_rules.yml
weights:
  resolution: 3.0
  source_type: 2.5
  seeders: 2.0
  size_fit: 1.5
  codec: 1.0
  release_group: 0.5

resolution_scores:
  "2160p": 1.0
  "1080p": 0.8
  "720p": 0.4
  null: 0.2

source_type_scores:
  "Remux": 1.0
  "BluRay": 0.9
  "BDRip": 0.8
  "WEB-DL": 0.7
  "WEBRip": 0.5
  null: 0.3

codec_scores:
  "x265": 0.9
  "HEVC": 0.9
  "x264": 0.8
  null: 0.4

release_group_preferred:
  - VCB-Studio
  - SweetSub
  - CHD
  - WiKi
  - FRDS
```

**seeders** 按分段给分：
- `seeders >= 50` → 1.0
- `20-49` → 0.8
- `5-19` → 0.5
- `1-4` → 0.2
- `0 或 None` → 0.0

**size_fit** 按期望大小给分（电影 1080p 期望 5-15 GB、电视剧单集期望 1-5 GB；超出区间按距离衰减）。

## 5. 输出

```python
@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate: BTCandidate
    score: float
    score_breakdown: dict[str, float]  # {"resolution": 0.8, "seeders": 1.0, ...}
    drop_reason: str | None            # None = 未被预过滤淘汰
```

评分器暴露两个函数：
- `filter_candidates(candidates, context) -> list[ScoredCandidate]`：已排序（score 降序），drop 的候选也在列表里但 `drop_reason != None`
- `pick_best(candidates, context) -> ScoredCandidate | None`：取第一个 `drop_reason is None` 的；没有就返回 `None`

`score_breakdown` 留给调试和后续可解释回包用，不在主流程消费。

## 6. 三条 BT 路径的接入

Codex 按顺序改：

1. `app/services/pure_bt.py`：把当前 `_rank_candidates()` 替换成 `pick_best(...)`，context 传 `media_kind="raw_bt"`。
2. `app/services/manage_bt_subscription.py::_scan_chat_once()`：把当前选源替换成 `pick_best(...)`，context 传订阅项的 `media_kind`。
3. 媒体型 BT 主链（`movie / series / anime`）：候选展示给用户时按 `score` 排序，不自动选；用户 `select <编号>` 仍由用户决定。

任意接入不改 downloader approval → confirm → dispatch 边界。

## 7. 可配置文件的加载策略

- 启动时读 `app/services/bt_scoring_rules.yml`（如果存在）到内存；文件缺失走内置最小集。
- 不做运行时 reload；改规则需重启。
- 不引入 YAML schema validation 框架；用内置 dataclass + 简单赋值，字段缺失时用内置默认值并打印一条中文 warning。

## 8. 分阶段落地

- **Phase 1**：新建 `app/services/bt_candidate_scorer.py`，实现 §2 结构 + §3 预过滤 + §4 评分 + §5 输出。内置最小规则集。写 15 条典型候选的 unit test。
- **Phase 2**：支持可选 `bt_scoring_rules.yml`；缺失 / 字段损坏时打印中文 warning，继续走内置。
- **Phase 3**：接入 `pure_bt.py`，跑 `tests/test_pure_bt.py` 全绿。
- **Phase 4**：接入 `manage_bt_subscription.py`，跑 `tests/test_manage_bt_subscription.py` 全绿。
- **Phase 5**：媒体型 BT 候选展示按 `score` 排序（只改排序，不改选择逻辑）。

## 9. 可测量退出条件

1. 三条 BT 路径都已接入共享评分器，`.venv/bin/python -m pytest -q tests/test_bt_candidate_scorer.py tests/test_pure_bt.py tests/test_manage_bt_subscription.py` 全绿。
2. 或本轮代码变更 < 20 行、只是为同一个 weight key 再加一条微调（走 `AGENTS.md §11` 停机规则）。

## 10. 不做清单

- 不引入 DSL / 规则语言
- 不用 LLM 判分或摘要
- 不做"质量评分器 + 自动 confirm"一条龙；命中后继续走 approval → confirm → dispatch 边界
- 不做站点白名单 / 黑名单（交给 Prowlarr / WebSource 适配层）
- 不做个人偏好学习（不收集 user feedback 做权重微调）
- 不做 `raw_bt` subscription（D-012 已禁）
