# docs/SERIES_ANIME_NAMING_PLAN.md (v1)

> 目的：把 `docs/NEXT_STEP.md` 的 `After this step` "series / anime 独立名称解析最小实现" 主线提前设计到位，Codex 可以照单施工。
>
> 本文件是**蓝图**，不是台账。落地后的详细闭环、focused tests、commit 轨迹继续走 `docs/SERIES_ANIME_NAMING_LOG.md`（Codex 按主线启动时自建）。
>
> 上游决策：`docs/DECISIONS.md` D-029。

## 1. 要解决的真实问题

当前 movie-first 主链假设用户发的就是"片名 [年份]"，`search_media` 按这个解析。但进入 `series / anime` 时，三处文本**不是同一种结构**：

1. 用户输入：`鬼灭之刃 S01E01` / `进击的巨人 第二季` / `名侦探柯南 1096`
2. 来源候选标题（来自 Prowlarr / WebSource）：`[SweetSub][Frieren][01][WebRip][1080p][AVC AAC][CHS][MP4]` / `鬼灭之刃.Demon.Slayer.S01E01.1080p.WEB-DL.x264-GROUP`
3. 下载完成后的文件名：任意命名，含季集信息或不含

任何一处不收敛成相同的结构化结果，TMDB 关联 / 追更 / 文件归集都会各自断裂。当前主线的最小目标是**提供一个可复用的解析步骤**，把三种文本映射到统一结构。

## 2. 输出数据结构

```python
@dataclass(frozen=True, slots=True)
class ParsedMediaName:
    title: str                    # 清洗后的主标题（中文或拉丁，优先中文）
    alt_titles: tuple[str, ...]   # 可选：原文里出现过的其它标题（罗马音、英文、别名）
    year: int | None              # 年份，来自方括号 [2024] 或独立 4 位数字
    season: int | None            # None 表示单集或 movie
    episode: int | None           # None 表示整季或 movie
    episode_end: int | None       # 多集合并（S01E01-03）时的结束集号
    quality_tags: tuple[str, ...] # 1080p / 2160p / WEB-DL / BluRay / HDR / 10bit 等
    source_group: str | None      # 制作组 / 字幕组（SweetSub / VCB-Studio / 国配）
    container: str | None         # mkv / mp4 / ass / srt 等
    media_kind: str               # "movie" | "series" | "anime" | "unknown"
    raw: str                      # 原始输入
    parser_confidence: float      # 0.0-1.0；见 §5
```

所有消费侧一律读这个结构，不再各自正则。

## 3. 解析步骤（parser-first）

固定 4 步流水线，不能顺序变：

1. **预处理**：
   - Unicode NFKC
   - 统一全角括号到半角
   - 剥离前缀发布组标签（`[SweetSub]` / `[VCB-Studio]`）并记到 `source_group`
   - 剥离后缀封装（`.mkv` / `.ass`）并记到 `container`
2. **主 regex**：顺序尝试以下模式，命中即停：
   - `S\d{1,2}E\d{1,3}(-\d{1,3})?` → season + episode(+end)
   - `第\s*(\d{1,3})\s*季` → season
   - `(\d{1,3})(话|話|集)` → episode
   - `EP?\s*(\d{1,3})` → episode
   - 末尾 `[\s.]\d{1,4}[\s.]` + 无上下文 season → 疑似单集（动漫常见），`parser_confidence *= 0.6`
3. **识别词 / 替换规则**（可配置文件，§4）：
   - 命中的 key 从标题里移除或替换
   - 用于处理 `国配` / `繁中` / `无字幕` / `双语` 这类噪音
   - 以及 `进击的巨人` ↔ `Attack on Titan` 这类跨语言映射（只用于 `alt_titles`，不改 `title`）
4. **后处理**：
   - 剩余主标题去尾部多余符号、空格、`-`、`.`
   - `title` 取最长的中文连续段；若无中文则取最长拉丁段
   - `quality_tags` 从剩余噪音里 grep 出 1080p / 2160p / WEB-DL / BluRay / HDR / 10bit / DV 等已知关键词
   - 计算 `parser_confidence`（命中主 regex = 0.8；识别词命中 +0.1；残留噪音 > 20% 字符 -0.2；等）

## 4. 可配置识别词 / 替换规则

- 文件位置：`app/services/naming_rules.yml`（新文件，YAML）
- 结构：
  ```yaml
  strip_tags:
    - 国配
    - 繁中
    - 无字幕
    - 中日双语
    - 简繁
    - CHT
    - CHS
  alt_titles:
    - primary: "进击的巨人"
      aliases: ["Attack on Titan", "Shingeki no Kyojin", "進撃の巨人"]
    - primary: "鬼灭之刃"
      aliases: ["Demon Slayer", "Kimetsu no Yaiba"]
  quality_whitelist:
    - 2160p
    - 1080p
    - 720p
    - WEB-DL
    - WEBRip
    - BluRay
    - BDRip
    - HDR
    - DV
    - 10bit
    - HEVC
    - x264
    - x265
  ```
- 读取时缓存；`naming_rules.yml` 不存在时走内置最小集合（`strip_tags` 仅 CHT/CHS，`quality_whitelist` 上面这些，`alt_titles` 为空）。
- 配置文件**不是**启动硬必填。

## 5. `parser_confidence` 的用处

- `>= 0.7`：进 TMDB 关联、自动导入、追更等主流程。
- `0.4 - 0.7`：进 TMDB，但请求 shared runtime 里显式 "澄清"（和现有 `clarification_state` 复用）。
- `< 0.4`：直接回用户"无法识别，请补片名 [年份] 或 S01E01 格式"，不进主流程。

## 6. 集成点（仅列清单，具体 diff 由 Codex 跑）

以下四处必须改成调用统一解析：

- `app/services/search_media.py::parse_query()` — 用户输入
- BT shared source adapter 里的候选标题清洗（当前在 `bt_sources.py`） — 来源候选
- `app/services/post_download_auto_import.py::_resolve_target_name()` — 下载完成文件名
- `app/services/import_to_library.py::_resolve_normalized_naming_truth()` — 命名真相

## 7. `.ass` 字幕同步评估

D-029 要求"动漫落地时同步评估 `.ass` 字幕"。当前 `app/services/subtitle_translator.py` 只处理 `.srt`。本主线需补：

1. `.ass` 文件识别（扩展名 + `[Script Info]` 头判定）
2. 简单事件行提取（`Dialogue: ...` 行里的最后一个字段是文本）
3. 翻译策略和 `.srt` 一致
4. 回写 `.ass` 时保留原 Style / Dialogue 时间轴，只替换 Dialogue 文本字段
5. 不做复杂样式改写、不处理 `.ssa`（旧格式）、不处理嵌入字幕（`.mkv` 内流）

`.ass` 支持在本主线内最小落地；更深的字幕能力（嵌入流、OCR、多语言）不在范围。

## 8. 分阶段落地

Codex 按这个顺序推，每阶段一个 commit：

- **Phase 1**：新建 `app/services/media_name_parser.py`，只实现 §2 结构 + §3 解析步骤（不含可配置识别词，先用内置最小集）。给 10 条典型输入的 unit test。
- **Phase 2**：加载 `naming_rules.yml` 可选配置；给 5 条跨语言 / 噪音输入的 unit test。
- **Phase 3**：把 §6 四个集成点全部切换到统一 parser，跑完整回归。不改 movie-first 的行为。
- **Phase 4**：扩 `subtitle_translator.py` 支持 `.ass`；给 2 条 `.ass` 输入的 unit test + 一条端到端翻译回写回归。
- **Phase 5**：在 `search_media` 的 clarification 入口按 §5 confidence 分流。

## 9. 可测量退出条件（任一触发即停）

1. §6 四处集成点都已切到 `ParsedMediaName`，且 `.venv/bin/python -m pytest -q tests/test_media_name_parser.py tests/test_search_media.py tests/test_import_to_library.py tests/test_post_download_auto_import.py tests/test_subtitle_translator.py` 全绿。
2. 或 Phase 1-5 已完成 3 个，剩余 2 个都涉及产品决策（例如 clarification 分流文案），此时停下来请用户确认。
3. 或本轮代码改动 < 20 行、只是对同一个规则表再加一条 `strip_tag` / `alt_title`，视为收益递减（走 `AGENTS.md §11` 停机规则）。

## 10. 不做清单

- 不做 MoviePilot 整套规则引擎 / DSL
- 不做嵌入字幕流 / `.ssa` / SRT → ASS 转换
- 不做多语言 LLM 猜测（parser-first）
- 不做运行时修改 `naming_rules.yml`（改完重启才生效）
- 不为 anime 专门做评分、也不加 AniDB / Bangumi 集成（那是另一条主线）
