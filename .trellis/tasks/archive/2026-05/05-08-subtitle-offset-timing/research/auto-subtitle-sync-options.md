# Research: auto-subtitle-sync-options

- Query: Research automatic subtitle synchronization approaches suitable for Luminarr's `subtitle-offset-timing` task; compare ffsubsync, alass, Subaligner, and one Whisper/ASR-based alignment approach; evaluate sync type solved, dependencies, offline suitability, language dependence, SRT/ASS support, integration complexity after existing `.zh.srt` / `.dual.ass` outputs, and whether timing changes are deterministic; end with an MVP recommendation and explicit first-implementation non-goals.
- Scope: mixed
- Date: 2026-05-08

## Findings

### Repo context

- 当前任务 PRD 明确把第一版目标限定为“固定 offset 校时”，并把“自动音频对齐 / ASR / 多段非线性修复”列为 out of scope：`.trellis/tasks/05-08-subtitle-offset-timing/prd.md:5`, `.trellis/tasks/05-08-subtitle-offset-timing/prd.md:16`, `.trellis/tasks/05-08-subtitle-offset-timing/prd.md:46`.
- 现有翻译链不会修改时间轴：
  - SRT 路径直接复用原 `block.timecode` 输出翻译后的 plain 字幕：`app/services/subtitle_translation_support.py:1250`.
  - ASS 路径只替换 dialogue 文本，保留原 `Dialogue:` 前缀中的 timing：`app/services/subtitle_translation_support.py:1300`.
- 当前输出命名真相：
  - 源 `.srt` -> plain `.zh.srt`：`app/services/subtitle_translation_support.py:171`.
  - 源 `.ass` -> plain `.zh.ass`：`app/services/subtitle_translation_support.py:173`.
  - 双语 sidecar 始终写成 `source_path.with_suffix(".dual.ass")`：`app/services/subtitle_translation_support.py:1502`.
- 仓库已经依赖 `ffmpeg/ffprobe` 做内嵌字幕探测，因此未来若接入基于音频的自动同步，不会是全新的媒体基础设施：`app/services/subtitle_translation_support.py:892`, `app/services/subtitle_translation_support.py:933`.

### Files found

- `.trellis/tasks/05-08-subtitle-offset-timing/prd.md` — 本任务边界，明确先做 deterministic 固定 offset，不做自动同步。
- `app/services/subtitle_translation_support.py` — 字幕发现、翻译、plain 输出与 `.dual.ass` sidecar 生成主链。
- `.trellis/spec/backend/subtitle-translation-contracts.md` — plain 字幕仍是 authoritative fallback，双语 ASS 是 sidecar，失败不能拖垮主链。
- `.trellis/spec/backend/quality-guidelines.md` — 该任务后续实现仍需保持主线验证门常绿。

### Code patterns

- `app/services/subtitle_translation_support.py:163-175`
  - 只把非中文字幕源字幕纳入翻译输入，并避开 `.dual.ass`，避免 sidecar 反向被当成输入。
- `app/services/subtitle_translation_support.py:1227-1265`
  - SRT 翻译是“文本替换 + 保留原时间码”，因此任何自动同步若在翻译前完成，会自然同时流入 `.zh.srt` 与 `.dual.ass`。
- `app/services/subtitle_translation_support.py:1277-1310`
  - ASS 翻译同样保留原 timing 前缀，说明“先同步源字幕，再翻译”比“生成后分别同步 `.zh.srt` / `.dual.ass`”更稳。
- `app/services/subtitle_translation_support.py:1502-1505`
  - `.dual.ass` 是旁路 sidecar，不是主真相文件；如果自动同步直接改 sidecar，需要额外保证 plain 输出同步一致。

### Tool comparison

#### ffsubsync

- What it solves:
  - 官方定位是“Language-agnostic automatic synchronization of subtitles with video”，核心是把字幕对到正确起点。
  - README 说明会尝试 framerate ratio 修正，支持 `--gss` 搜索最佳比例；因此它覆盖“全局 offset + 线性帧率比漂移”，但不覆盖中段 breaks/splits。
  - Limitations 明说“Handling breaks and splits outside of the beginning and ending segments is left to future work.”
- Dependencies:
  - 需要 `ffmpeg`。
  - Python 包安装简单：`pip install ffsubsync`。
  - 依赖 VAD（WebRTC 或 auditok）和 FFT；对本 repo 来说属于中等偏低集成成本。
- Offline suitability:
  - 适合离线；安装后本地跑即可，不依赖在线 API。
- Language dependence:
  - 语言无关。它对字幕只看 cue on/off，对音频做 VAD，不需要理解文本语义。
  - 还支持拿另一份已同步的参考字幕做基准，即使语言不同也可用。
- SRT/ASS support:
  - README/示例明显以 SRT 为主。
  - Release notes 说明已有“Retain ASS styles”和“Use output extension to determine output format”，说明 ASS 处理存在，但文档心智仍是 SRT-first。
  - 结论：SRT 非常适合；ASS 可行但应视为“有支持、需本仓库自行验证”的层级。
- Integration after `.zh.srt` / `.dual.ass`:
  - 如果对成品 `.zh.srt` / `.dual.ass` 分别跑，理论上可行，但不保证两次运行得到完全一致的 timing map，且 `.dual.ass` 支持在上游文档里不够一等公民。
  - 更适合集成在“翻译前”的英文源字幕阶段：先把 source subtitle 对齐，再走现有翻译逻辑，一次生成 timing 一致的 plain + sidecar。
- Determinism:
  - 高，属于算法型工具；在固定输入、固定版本、固定 VAD backend/flags 下应当可重复。
  - 这是基于 README 的算法描述做的推断；上游没有给出形式化 deterministic 保证。
- Fit for Luminarr:
  - 很适合作为“未来可选自动同步 backend”的第一候选，前提是主诉求仍是整体偏移/帧率差，而不是中段断裂。

#### alass

- What it solves:
  - 官方明确列出可自动纠正：
    - `constant offsets`
    - `splits due to advertisement breaks, directors cut, ...`
    - `different framerates`
  - 还支持 `--no-splits` 退化成只做快速全局平移。
  - 这是四个选项里最明确覆盖“global offset + split-aware nonlinear-ish cases”的传统算法工具。
- Dependencies:
  - 官方 CLI 是 Rust，`cargo install alass-cli`。
  - 还需要 `ffmpeg` / `ffprobe`；并且 voice-activity module 编译时要 C compiler。
  - 对 Python 3.12 单进程仓库来说，运维和安装门槛高于 ffsubsync。
- Offline suitability:
  - 适合离线；下载二进制或编译后即可本地跑。
- Language dependence:
  - 官方明确写明“language-agnostic”，甚至可以把错误字幕对到不同语言的参考字幕。
- SRT/ASS support:
  - 官方明确支持 `.srt`, `.ssa` / `.ass`, `.idx`。
  - 这点比 ffsubsync 对 `.dual.ass` 的适配确定性更高。
- Integration after `.zh.srt` / `.dual.ass`:
  - 如果未来真的需要 split-aware 自动同步，alass 是最适合在 source subtitle 阶段接入的传统 CLI。
  - 不建议直接对生成后的 `.zh.srt` 和 `.dual.ass` 各跑一次：默认 split-aware 行为可能引入/移除 break，两个文件独立重写后更容易发生细节漂移。
  - 若未来要接它，最好是“对源英文字幕跑 alass -> 用对齐后的源字幕继续现有翻译/双语渲染”。
- Determinism:
  - 很高。它是显式算法/动态规划路径，没有生成式组件。
  - 同样属于根据上游算法描述做的工程推断。
- Fit for Luminarr:
  - 能力强，但代价也更大：Rust CLI、GPL-3.0、最新 release 仍停在 2019-10-10。
  - 更像“如果后续实测证明 split/director's cut/广告断段是高频痛点，再认真引入”的 phase-2 候选，而不是当前 repo 的 first move。

#### Subaligner

- What it solves:
  - 官方把对齐定义成“dual-stage process with a Bidirectional Long Short-Term Memory network trained upfront”。
  - CLI 区分：
    - `-m single`: “high-level shift with lower latency”
    - `-m dual`: “low-level shift with higher latency”
  - 另有实验性 `stretching`，说明它不仅做全局平移，也能走更细粒度的段级修正。
- Dependencies:
  - 基础安装需要 `FFmpeg`。
  - 基础安装是 Python 包：`pip install subaligner`。
  - 但额外能力需要更多依赖：
    - `subaligner[llm]` 用于 translation/transcription
    - `subaligner[stretch]` / `subaligner[harmony]` 需要 `eSpeak`
    - Python 3.12+ 下这些 extras 还需要 patched `aeneas`
  - 这对 Luminarr 当前 Python 3.12 环境是明显复杂化。
- Offline suitability:
  - 基础对齐可离线。
  - 如果启用 transcription/translation 或某些模型能力，通常还要先拉模型；离线部署准备成本比 ffsubsync/alass 高。
- Language dependence:
  - 基础自动对齐没有像 WhisperX 那样要求显式语言模型选择，语言依赖性低于纯 ASR 管线。
  - 但转录/翻译路径已经开始进入模型和语言配置领域，不再是“纯 timing 工具”。
- SRT/ASS support:
  - 官方支持格式很广，包括 `SubRip` 和 `(Advanced) SubStation Alpha`。
  - 还能输出 `.json`，这对未来如果想拿它做“生成 timing map，再由仓库自己回写格式”有一定吸引力。
- Integration after `.zh.srt` / `.dual.ass`:
  - 比 ffsubsync/alass 更像一个“字幕处理平台”而不是小而确定的 sync helper。
  - 直接接在现有 import-time translation 主线上，复杂度偏高：要决定 single 还是 dual、是否 stretch、是否允许 JSON downstream、以及在 Python 3.12 下怎么装 extras。
  - 若后续真的要做更细粒度自动同步，它比 WhisperX 更接近可直接使用的现成产品，但仍明显超出当前 MVP。
- Determinism:
  - 中等。基础 DNN 推理通常可重复，但比 ffsubsync/alass 少了“纯算法、纯规则”的确定性。
  - 若开启 stretch/transcribe/translation，环境差异带来的结果波动风险更高。
- Fit for Luminarr:
  - 能力面比 ffsubsync 宽，安装/维护面也明显更重，不符合当前任务“最小实现、无新依赖”的节奏。

#### WhisperX / ASR-based alignment pipeline

- What it solves:
  - WhisperX 不是“同步已有字幕”的轻量 CLI，而是 ASR + forced alignment 管线。
  - 官方强调 `word-level timestamps`，并展示通过 `wav2vec2` forced alignment 提高时间戳精度。
  - 这类方案更适合：
    - 原字幕 timing 严重损坏
    - 需要词级/句级重建时间轴
    - 甚至没有可用字幕，需要先转写
  - 它确实能覆盖非线性 drift，但做法已经接近“重做时间轴”而不是“修一下现有字幕”。
- Dependencies:
  - `pip install whisperx`，但官方同时提到可能还要 `ffmpeg`, `rust`，并强烈面向 GPU/CUDA。
  - 可用 CPU 跑，但官方文档大量优化点都围绕 GPU memory / batch size / compute type。
  - 对现有仓库与 Docker Compose 部署习惯来说，这是最重的方案。
- Offline suitability:
  - 模型缓存完后可本地离线运行，这是可行的。
  - 但首次部署、模型缓存、GPU/CPU 性能差异都让它更像一个单独子系统。
- Language dependence:
  - 明显语言相关。
  - 官方明确写：
    - alignment model 是 language-specific
    - 默认只为 `{en, fr, de, es, it}` 提供 torchaudio models
    - 其他语言要自己去 Hugging Face 找 phoneme-based ASR model
  - 如果字幕源是英文而视频语音是英文，这还算可控；一旦要扩展多语种，复杂度会迅速上升。
- SRT/ASS support:
  - 官方示例明确能输出 `.srt` 并高亮单词级 timing。
  - 但 README TODO 明说：`Subtitle .ass output <- bring this back (removed in v3)`。
  - 结论：对本 repo 的 `.dual.ass` 现状极不友好；如果接入，必须由仓库自己负责把新 timing 回写到 ASS/dual ASS。
- Integration after `.zh.srt` / `.dual.ass`:
  - 最不适合“对现成 `.zh.srt` / `.dual.ass` 做小修小补”。
  - 真要接，合理方式应是：
    1. 对视频音频跑 ASR+alignment 得到英文 transcript/word timings。
    2. 把现有英文 source subtitle 行与 transcript 对齐。
    3. 再把 recovered timings 套回翻译后的 plain / dual outputs。
  - 这已经不是“加一个 CLI backend”能完成的工作，而是新子系统。
- Determinism:
  - 低到中等。
  - 受 ASR 模型、compute type、batch size、language model、硬件路径影响更大；它不是当前任务想要的 deterministic timing shifter。
- Fit for Luminarr:
  - 适合未来“高成本、高能力”的专项能力，不适合本轮任务，也不适合作为第一批自动同步实验。

### Integration recommendation for this repo

- 如果未来真的尝试自动同步，不要把工具直接套在最终 `.zh.srt` 和 `.dual.ass` 成品上作为主路径。
- 更稳的接入点是“翻译前的 source subtitle”：
  - 先对英文 source `.srt/.ass` 做同步。
  - 再沿用现有翻译逻辑生成 plain 输出和 `.dual.ass` sidecar。
  - 这样可以天然保持两个产物 timing 一致，也不会让 sidecar 成为新的 timing truth。
- 在这条接入思路下：
  - `ffsubsync` 更适合将来做“轻量、可选、先试试”的自动同步 backend。
  - `alass` 更适合将来做“当 split/director's cut 真的成为高频问题时”的增强版 backend。
  - `Subaligner` 和 `WhisperX` 都应视为“下一阶段甚至更后”的体系化方案，而不是本任务延伸实现。

### Recommended MVP for Luminarr

- 推荐 MVP 仍然是当前 PRD 已定义的 repo-native 固定 offset：
  - 只做 deterministic 的正负毫秒平移；
  - 一次性同时作用于 plain 输出和 `.dual.ass`；
  - 不引入新依赖，不引入外部 CLI，不引入模型下载，不改翻译 prompt，不改 chunk/resume 协议。
- 如果要为“未来自动同步”留路线，建议只留非常薄的一层 seam：
  - 让 timing adjustment 逻辑独立于翻译文本逻辑；
  - 后续如要接 `ffsubsync` / `alass`，就把“自动求得的 offset / 对齐后源字幕”喂给同一套 timing rewrite helper。
- 自动同步方向的优先级建议：
  1. 第一阶段：固定 offset（本任务）。
  2. 第二阶段：可选 `ffsubsync` source-subtitle pre-sync，限定 SRT-first、soft-fail、operator opt-in。
  3. 第三阶段：只有在真实样本反复证明中段 split/nonlinear 问题频繁时，再评估 `alass`。
  4. ASR/Whisper 系列单独立项，不作为 offset 功能自然延伸。

## Caveats / Not Found

- 没有在 ffsubsync README 主文档里看到与 alass/Subaligner 同等级清晰的 ASS 支持说明；目前主要依据 release notes 中的 “Retain ASS styles” 和 “Use output extension to determine output format” 判断其具备一定 ASS 处理能力，因此把它记为“可用但需本仓库自测”。
- determinism 这一项，四个上游都没有给出严格形式化承诺；文中关于“高/中/低”的判断是基于它们公开的算法/模型结构做的工程推断，不是上游明文 SLA。
- 本次没有进一步调研字幕同步工具的 license 兼容细节 beyond repo license tags；若未来真要把 `alass`（GPL-3.0）作为 bundled dependency，而不是 operator-installed optional binary，需要单独做一次发布/分发层面的 license 评估。
- 对本任务来说，最关键的不是“哪家自动同步最准”，而是“首版是否应该引入自动同步”。基于当前 PRD、现有代码结构和仓库约束，答案仍然是否定的。

### External references

- ffsubsync
  - GitHub README / latest release 0.4.31 (2025-11-24): https://github.com/smacke/ffsubsync
  - Releases: https://github.com/smacke/ffsubsync/releases
- alass
  - GitHub README / latest release Alass 2 (2019-10-10): https://github.com/kaegi/alass
  - `alass-cli` 2.0.0 crate metadata: https://docs.rs/crate/alass-cli/latest/source/Cargo.toml.orig
- Subaligner
  - Docs 0.3.12: https://subaligner.readthedocs.io/en/latest/
  - Usage docs: https://subaligner.readthedocs.io/en/stable/usage.html
  - GitHub latest release v0.3.12 (2026-02-05): https://github.com/baxtree/subaligner
- WhisperX
  - GitHub README / latest release v3.8.5 (2026-04-01): https://github.com/m-bain/whisperX

### Related specs

- `.trellis/spec/backend/index.md`
- `.trellis/spec/backend/subtitle-translation-contracts.md`
- `.trellis/spec/backend/quality-guidelines.md`
