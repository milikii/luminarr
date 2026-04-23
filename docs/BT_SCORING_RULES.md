# BT Scoring Rules (v1)

> 目的：给操作者和 fork 维护者一份**短说明**，知道 `app/services/bt_scoring_rules.yml` 里每个字段怎么调，不用先翻长蓝图。

## 1. 文件位置

当前规则文件：

```text
/home/alex/projects/luminarr/app/services/bt_scoring_rules.yml
```

当前代码会在启动时读取它；文件缺失或字段损坏时，会打印中文 warning，并回退到内置默认值。

## 2. 默认风格

当前默认风格是：

1. 片名精确度优先
2. 来源站点偏好
3. 资源类型优先
4. 分辨率
5. 体积合理性
6. 做种人数次之
7. 编码 / 发布组小修正

这套默认值更适合当前以国外 PT 站点为主的索引器画像。

## 3. 你最常改的字段

### `weights`

控制每个评分信号的**总重要性**。

当前默认值：

```yaml
weights:
  title_relevance: 8.0
  source_site: 1.25
  source_type: 3.0
  resolution: 2.5
  seeders: 1.0
  size_fit: 1.5
  codec: 0.75
  release_group: 0.5
```

怎么理解：

- 想更保守地“先保证片名对”：提高 `title_relevance`
- 想更看重站点：提高 `source_site`
- 想更看重资源质量：提高 `source_type` / `resolution`
- 想更看重下载成功率：提高 `seeders`

### `source_site_preferred`

控制**来源站点偏好**。

当前默认值：

```yaml
source_site_preferred:
  - PTP
  - BTN
  - PTerClub
  - HDBits
  - MTV
```

作用：

- 同类资源之间，优先把这些站点往前排
- 它不会越过“片名不对”的硬边界
- 更适合做 tie-break 和偏好排序，不适合拿来压过标题匹配

如果你自己的索引器里某些站更可信，就把它们往前放。

### `source_type_scores`

控制**资源类型好坏**。

当前默认值：

```yaml
source_type_scores:
  "Remux": 1.0
  "BluRay": 0.9
  "BDRip": 0.8
  "WEB-DL": 0.7
  "WEBRip": 0.5
  null: 0.3
```

如果你不想总是先下 BluRay / Remux，可以：

- 提高 `WEB-DL`
- 降低 `BluRay` / `Remux`

### `resolution_scores`

控制**分辨率偏好**。

如果你更偏向省空间，可以把 `1080p` 提高到接近 `2160p`，甚至让它超过 `2160p`。

### `release_group_preferred`

控制**发布组偏好**。

这个适合做小修正，不建议把它权重调得太高。

## 4. 两条别乱改的原则

### 不要把 `seeders` 调得比 `title_relevance` 还高

否则很容易回到“热门错片排前”的老问题。

### 不要把 `source_site` 当成硬过滤

它应该只是偏好，不是白名单。

否则你会错过别的站点里更好的同片名资源。

## 5. 推荐调法

### 想更像 MoviePilot 的“保守电影偏好”

- 保持 `title_relevance` 最高
- `source_type` 略高于 `resolution`
- `seeders` 保持低于 `source_type`

### 想更偏下载成功率

- 小幅提高 `seeders`
- 不要超过 `title_relevance`
- 最多和 `resolution` 接近

### 想更偏小体积

- 降低 `resolution`
- 提高 `size_fit`
- 同时把 `WEB-DL` 稍微抬一点

## 6. 改完怎么验证

最小验证：

```bash
.venv/bin/python -m pytest -q tests/test_bt_candidate_scorer.py
```

仓库质量入口：

```bash
make quality
```

如果你要看真实搜索排序变化，再去跑当前 search smoke 或真实查询。
