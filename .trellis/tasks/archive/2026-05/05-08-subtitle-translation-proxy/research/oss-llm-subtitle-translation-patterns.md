# OSS patterns for LLM subtitle translation

Date: 2026-05-08

## Scope

Research open-source projects that translate subtitles through LLM or model APIs and extract implementation patterns relevant to Luminarr's current subtitle translation path.

## Repositories reviewed

### 1. machinewrapped/gpt-subtrans

Repo: https://github.com/machinewrapped/gpt-subtrans

Observed patterns:
- Supports `.srt`, `.ssa`/`.ass`, and `.vtt`
- Can target any OpenAI-compatible API endpoint
- Persists a project file so interrupted translation can resume
- Exposes rate limiting and movie-name context as first-class options
- Supports format conversion while translating

Why it matters for us:
- The resumable project-file approach is the cleanest answer to our current "one chunk timeout kills the whole run" problem.
- Explicit rate limiting and resumability are more important than raw throughput for long subtitle jobs.

### 2. rockbenben/subtitle-translator

Repo: https://github.com/rockbenben/subtitle-translator

Observed patterns:
- Supports `.srt`, `.ass`, `.vtt`, and `.lrc`
- Uses chunked compression plus parallel processing for speed
- Treats surrounding context as an explicit tuning parameter
- Supports bilingual output placement
- Supports many LLM backends plus custom LLM endpoints

Why it matters for us:
- Separating "concurrent lines" from "context lines" is a useful design: translation quality and timeout risk can be tuned independently.
- Their warning that smaller/less-stable models can misalign output matches the failure mode we already see.

### 3. Cerlancism/chatgpt-subtitle-translator

Repo: https://github.com/Cerlancism/chatgpt-subtitle-translator

Observed patterns:
- Built specifically around line-based subtitle translation
- Removes SRT structural overhead before sending requests, then reconstructs output after translation
- Uses structured output to force one-to-one line mapping
- Supports OpenAI-compatible providers, prompt caching, progress resumption, and streaming logs
- Has optional moderation pre-check to avoid wasting requests on likely refusals

Why it matters for us:
- This is the closest match to our current architecture.
- "Line-based batching + structured output + resumable progress" is the strongest pattern to borrow directly.

### 4. TestersNightmare/SubtitleCAT

Repo: https://github.com/TestersNightmare/SubtitleCAT

Observed patterns:
- Extracts subtitles from MP4/MKV with FFmpeg
- Translates via Gemini
- Generates bilingual ASS output
- Supports multiple API keys with automatic failover for rate limit / transient upstream errors
- Optimized for one-click batch workflows

Why it matters for us:
- API key rotation / failover is a practical answer when the provider is flaky.
- Bilingual ASS as a first-class artifact is common enough that our current `.dual.ass` output direction looks right.

### 5. gnehs/subtitle-translator

Repo: https://github.com/gnehs/subtitle-translator

Observed patterns:
- A lighter-weight CLI that translates subtitle files through ChatGPT
- Keeps the workflow simple: input subtitle -> model translation -> output folder
- Good example of the minimum viable OpenAI-backed subtitle translator

Why it matters for us:
- Useful as a lower-complexity baseline: it shows what can stay simple, and what complexity only appears once you care about resumability, bilingual output, and flaky providers.

## Common patterns across OSS projects

### 1. Chunking is mandatory

Nobody ships "whole subtitle file in one request" as the normal path.

Common variants:
- Fixed line count per batch
- Fixed subtitle-block count per batch
- Context window around each batch
- Retry with smaller chunks after timeout or line-count mismatch

Implication for Luminarr:
- Our current fixed chunk flow is directionally correct.
- The missing piece is durable resume state after a failed chunk.

### 2. One-to-one mapping is treated as a hard contract

Projects that work well all protect timing by enforcing:
- input line count == output line count
- structured JSON or schema-validated output
- retry or split when line counts drift

Implication for Luminarr:
- Our current strict count checking is right.
- If we relax anything, it should be only in retry strategy, not the mapping contract.

### 3. Context is useful, but it must be bounded

Common practice:
- send movie/show title
- send nearby lines
- avoid sending too much subtitle boilerplate

Implication for Luminarr:
- Metadata title + trusted-name map is good.
- If we expand context, prefer adjacent dialogue lines instead of larger whole-file prompts.

### 4. Resumability matters more than peak speed

The most production-friendly tools all have some form of:
- project state file
- partial progress cache
- resumable CLI run
- visible progress logging

Implication for Luminarr:
- This is the main gap in our current implementation.
- Right now a mid-run timeout wastes already successful chunks.

### 5. Bilingual output is a common first-class feature

Observed outputs:
- translated-only `.srt`
- bilingual `.ass`
- optional original/translated ordering

Implication for Luminarr:
- Keeping both `.zh.srt` and `.dual.ass` is aligned with existing OSS practice.

### 6. Provider/network instability is expected, not exceptional

Common mitigations:
- per-chunk retries
- exponential or bounded backoff
- RPM throttling
- multi-key rotation
- progress save + resume
- configurable proxy / OpenAI-compatible endpoint

Implication for Luminarr:
- `SUBTITLE_TRANSLATION_USE_PROXY` should stay explicit and operator-controlled.
- We likely need retry plus durable progress before we need anything more exotic.

## What looks most worth copying into Luminarr

### Highest-value

1. Resumable per-file progress state
- Save completed chunk indexes and partial translated blocks beside the target subtitle.
- Resume from the first unfinished chunk instead of restarting the whole job.

2. Structured-output enforcement at chunk level
- Keep one-to-one line mapping strict.
- Fail one chunk, not the whole file state.

3. Progress logging
- Emit `chunk X/Y` to logs or job events.
- This shortens debugging and reduces "is it stuck?" ambiguity.

### Medium-value

4. Config split between batch size and context size
- Current code effectively only exposes chunk size.
- Exposing adjacent-context size separately would let us tune quality without inflating each translation request too much.

5. Rate limiting
- Useful if provider throttling becomes a repeat issue.

### Lower-value for now

6. Multi-provider or multi-key failover
- Useful, but probably overkill before resumability is fixed.

## Recommended direction for our current codebase

For the current Luminarr subtitle path, the safest next step is:

1. Keep the current `.srt` -> `.zh.srt` + `.dual.ass` outputs
2. Keep strict line-count validation
3. Add durable chunk-progress persistence
4. Add resume-from-last-good-chunk behavior
5. Record chunk progress and failures into operator-visible logs/events
6. Leave provider/key failover for later unless upstream instability gets worse

## Source notes

- machinewrapped/gpt-subtrans README + wiki: multi-format support, OpenAI-compatible endpoint support, project-file resume, rate limit, movie-name context
- rockbenben/subtitle-translator README: chunked compression, parallel processing, bilingual output, context tuning, multi-model support
- Cerlancism/chatgpt-subtitle-translator README: structured output, prompt caching, line-based batching, progress resumption
- TestersNightmare/SubtitleCAT README: FFmpeg extraction, bilingual ASS, multi-key failover
- gnehs/subtitle-translator README: minimal ChatGPT-based subtitle translation flow, translated output folder, lighter-weight CLI baseline
