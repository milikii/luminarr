# brainstorm: 翻译线

## Goal

定义下一条要推进的翻译主线，先锁定用户价值、入口场景和边界，再进入实现阶段，避免把现有字幕翻译、成人元数据中文化和 Telegram 展示翻译混成一锅。

## What I already know

* 用户明确要“开翻译线”。
* 用户已确认本轮唯一主线是：字幕导入翻译。
* 用户已确认本轮来源边界只覆盖：外挂字幕与内嵌字幕；不围绕其他来源扩展。
* 用户判断 PT 资源整体命名较规范，通常自带 `sub` 字幕，因此本轮不把“扩更多字幕来源”当成核心价值。
* 用户已确认本轮先打 `译文质量`，且优先处理：
  - 专名/术语
  - 字幕腔/口语感
* 用户新增硬要求：电影/剧集的人名不能只靠模型机器翻译，必须联网获取更常见的中文名，用户点名的候选来源包括 Wiki / 豆瓣。
* 仓库里已经有字幕翻译服务：`app/services/subtitle_translator.py`，目前用于导入阶段的字幕中文化。
* 仓库里已经有成人元数据翻译服务：`app/services/adult_metadata_translation.py`，目前用于成人候选结果展示前的中文字段补齐。
* `app/main.py` 已经把上面两条能力接进运行主线。
* `.trellis/spec/backend/bt-source-contracts.md` 已经定义了成人元数据翻译边界、失败回退和 Telegram formatter 的职责约束。

## Assumptions (temporary)

* “翻译线”大概率是要继续增强现有翻译能力，而不是从零引入新的第三方翻译体系。
* 本轮字幕翻译应继续复用现有 `SubtitleTranslatorService` / `subtitle_translation_support.py` 主路径，不另起独立翻译框架。
* 本轮不会把“支持新的字幕来源类型”作为目标，而是只在现有外挂/内嵌字幕路径上优化体验。
* 这轮不是单纯 prompt 润色；至少要解决“人名/专名可信来源”和“更像字幕的表达风格”两个问题。
* 若范围涉及 Telegram 交互文案或候选展示，需要继续遵守现有 service-layer / formatter 边界。

## Open Questions

* 当前待实现收口点：
  - 现有 metadata sidecar 还未写入 `tmdb.media_type`，需要补齐以支持 title-linked person-name lookup
  - 需要决定本轮是否先只做 TMDB-first，还是同时落最小 Wikidata fallback

## Requirements (evolving)

* 只做字幕导入翻译主线，不并行改成人元数据翻译或普通影视展示翻译。
* 只覆盖外挂字幕与英文内嵌字幕，不扩新的字幕来源类型。
* 保持现有翻译配置入口复用优先，避免无必要新增配置面。
* 保持失败软降级，不因为翻译失败阻断主业务路径。
* 对电影/剧集相关人名，不允许只靠模型自由翻译；若要输出中文名，必须来自联网可验证来源或多来源共识。
* 若人名没有可靠中文名来源，优先保留原文，而不是硬音译。
* 人名联网解析范围只处理“已确认媒体身份”可关联到的 cast/crew 常见人名，不做任意字幕行的完整 NER。
* 译文质量方案采用“强 prompt + 轻预处理”主线：先构建可信 name map，再把 name/term 约束注入逐行翻译请求。
* 本轮不做 Douban scraping。

## Locked Decisions

* 人名来源优先级：`TMDB zh-CN credits -> Wikidata/Wikipedia fallback -> 原文保留`
* MVP 触发范围：依赖 `.metadata.json` 已确认的 TMDB identity，不做无身份上下文的全量联网猜名
* 质量方案：优先解决
  - 专名/术语的可信映射
  - 更自然的字幕口语感 / 字幕腔
* 研究结论文件：
  - `research/person-name-sources.md`
  - `research/subtitle-quality-patterns.md`

## Acceptance Criteria (evolving)

* [ ] 明确本轮字幕翻译的唯一切入价值、用户入口和 out-of-scope。
* [ ] 明确影视人名联网来源策略与回退策略。
* [ ] 形成可执行的实现范围，能进入 Phase 2。
* [ ] 已知依赖边界、现有能力复用点和验证口径被记录清楚。

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* 本轮不同时重做所有翻译相关能力。
* 本轮不默认扩到成人元数据翻译或普通影视/PT 展示翻译。
* 本轮不把“扩大字幕来源覆盖面”当作目标，不额外支持新的来源类型。
* 本轮不默认引入新的翻译供应商、缓存层或独立翻译中台，除非后续范围确认确有必要。
* 本轮不默认把任意字幕行里的所有实体识别都做成完整 NER 系统，除非研究后发现这是最低可行路径。

## Technical Notes

* 已检查：
  - `app/main.py`
  - `app/services/subtitle_translator.py`
  - `app/services/subtitle_translation_support.py`
  - `app/services/adult_metadata_translation.py`
  - `.trellis/spec/backend/bt-source-contracts.md`
  - `docs/NEXT_STEP.md`
  - `tests/test_subtitle_translator.py`
* 当前仓库刚结束上一条 PT / adult BT 主线，新的翻译线需要作为独立 task 推进。
