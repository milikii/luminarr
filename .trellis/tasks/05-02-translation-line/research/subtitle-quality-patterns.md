# Research: subtitle-quality-patterns

- Query: Research practical quality-improvement patterns for AI subtitle translation in a PT-style import pipeline that only handles external and embedded English subtitles; focus on proper nouns/terms, natural Chinese subtitle tone, and preserving line-by-line JSON output; compare prompt-only, prompt+light preprocessing, and prompt+post-check.
- Scope: mixed
- Date: 2026-05-02

## Findings

### Files found

- `.trellis/tasks/05-02-translation-line/prd.md` — task scope and acceptance bar for the translation line.
- `app/services/subtitle_translator.py` — service shell for import-time subtitle translation.
- `app/services/subtitle_translation_support.py` — subtitle detection, SRT/ASS parsing, chunking, request building, JSON parsing, and rendering.
- `tests/test_subtitle_translator.py` — executable contract for current selection, chunking, and reconstruction behavior.
- `docs/DECISIONS.md` — product-level truth that subtitle translation is post-import enhancement and must fail soft.
- `.trellis/spec/backend/bt-source-contracts.md` — nearby translation-boundary precedent for fail-soft user-facing translation paths.
- `.trellis/spec/backend/quality-guidelines.md` — repo verification and evidence discipline.

### Current pipeline shape

- Only external subtitle files or extractable embedded English text streams are eligible; Chinese external or embedded subtitles short-circuit to skip. Code patterns:
  - `app/services/subtitle_translation_support.py:560` resolves external-first, then embedded English.
  - `app/services/subtitle_translation_support.py:606` prefers Chinese embedded skip over English extraction.
  - `app/services/subtitle_translation_support.py:617` and `:626` classify Chinese/English subtitle labels heuristically.
- The model currently sees only `movie_title` and `source_lines`; there is no glossary, adjacent-line context, or approved-name payload. Code patterns:
  - `app/services/subtitle_translation_support.py:329` builds the current prompt.
  - `app/services/subtitle_translation_support.py:339` sends only `movie_title`, `source_lines`, and generic rules.
- Structure is already protected outside the model, which is the right architectural shape for subtitle work:
  - `app/services/subtitle_translation_support.py:352` requires equal-length translations.
  - `app/services/subtitle_translation_support.py:1007` parses a `translations` array from model output.
  - `app/services/subtitle_translation_support.py:866` reconstructs SRT blocks locally.
  - `app/services/subtitle_translation_support.py:902` reconstructs ASS dialogue lines locally.
- Both SRT and ASS are translated in fixed 60-unit chunks:
  - `app/services/subtitle_translation_support.py:815` chunks blocks generically.
  - `app/services/subtitle_translation_support.py:884` and `:920` set chunk size to `60`.
  - `tests/test_subtitle_translator.py:93` verifies `[60, 2]` chunking behavior for a 62-line SRT.
- Metadata title is already available as context and user-facing truth:
  - `app/services/subtitle_translation_support.py:546` reads metadata-backed `movie_title`.
  - `app/services/subtitle_translation_support.py:1041` pulls the title from metadata JSON.
  - `tests/test_subtitle_translator.py:54` verifies summary text prefers metadata title.
- Product truth is fail-soft, not block-import:
  - `docs/DECISIONS.md:117` records subtitle auto-translation as a post-import enhancement.
  - `docs/DECISIONS.md:123` states subtitle failure must be explicit but must not roll back import success.

### Related specs

- `.trellis/spec/backend/bt-source-contracts.md`
  - The adult metadata translation contract already establishes a soft-fail translation boundary and a “trusted localized field beats free translation” mindset. That pattern is directly reusable for subtitle proper nouns.
- `.trellis/spec/backend/quality-guidelines.md`
  - Any implementation of these ideas should add focused tests for request shaping, glossary enforcement, and JSON/line-count safety instead of relying on prompt text alone.

### External references

- OpenAI, "Structured model outputs" (accessed 2026-05-02)
  - URL: `https://developers.openai.com/api/docs/guides/structured-outputs`
  - Useful lines: schema-constrained output avoids missing keys and invalid values, and reduces the need for strong JSON-only prompt wording (`turn1view0` lines 628-642).
- OpenAI, "Prompting" (accessed 2026-05-02)
  - URL: `https://developers.openai.com/api/docs/guides/prompting`
  - Useful lines: keep tone/role in system message, put task details/examples in user messages, and rerun evals whenever prompts change (`turn1view2` lines 677-682).
- TMDB, "Languages" + translation endpoints (updated 7 months ago; accessed 2026-05-02)
  - URLs:
    - `https://developer.themoviedb.org/docs/languages`
    - `https://developer.themoviedb.org/reference/movie-translations`
    - `https://developer.themoviedb.org/reference/translations` (person translations)
    - `https://developer.themoviedb.org/reference/tv-series-translations`
  - Useful lines: TMDB says most metadata localizes, but person names and characters are still major gaps (`turn2view0` lines 54-59). Practical implication: title zh can come from TMDB reliably, but person-name zh cannot be assumed from `language=zh-CN` alone.
- Netflix, "Chinese (Simplified) Timed Text Style Guide" (change log current through 2025-07-04; accessed 2026-05-02)
  - URL: `https://partnerhelp.netflixstudios.com/hc/en-us/articles/215986007-Chinese-Simplified-Timed-Text-Style-Guide`
  - Useful lines:
    - `16` chars per line, dialogue normally kept to `2` lines (`turn4view3` lines 23-25, 214-218; `turn4view2` lines 209-213).
    - Use official or well-known translations for titles; otherwise transliterate (`turn5view0` lines 196-200).
    - Match tone, keep profanity severity equivalent, avoid swapping brands/companies/famous people for other names (`turn5view0` lines 202-207).
    - Use Chinese punctuation/quotes consistently (`turn4view4` lines 135-149).
- Mota et al., "Fast-Paced Improvements to Named Entity Handling for Neural Machine Translation" (EAMT 2022)
  - URL: `https://aclanthology.org/2022.eamt-1.17/`
  - Abstract takeaway: separate named-entity recognition/translation plus masking/placeholders improved quality in `38.6%` of test cases without changing the underlying NMT component (`turn8search1`).
- Gaido et al., "Who Are We Talking About? Handling Person Names in Speech Translation" (IWSLT 2022)
  - URL: `https://aclanthology.org/2022.iwslt-1.6/`
  - Abstract takeaway: person names are a high-impact failure mode that can distort meaning, and need explicit mitigation rather than generic translation (`turn8search0`).
- Fernandes et al., "Measuring and Increasing Context Usage in Context-Aware Machine Translation" (ACL 2021)
  - URL: `https://aclanthology.org/2021.acl-long.505/`
  - Abstract takeaway: inter-sentential context matters, but adding more context has diminishing returns (`turn7search0`).
- Bogoychev and Chen, "Terminology-Aware Translation with Constrained Decoding and Large Language Model Prompting" (WMT 2023)
  - URL: `https://aclanthology.org/2023.wmt-1.80/`
  - Abstract takeaway: a translate-then-refine pattern with terminology constraints improves terminology recall, and LLM refinement helps when terminology is violated (`turn9search0`).
- Ki and Carpuat, "Guiding Large Language Models to Post-Edit Machine Translation with Error Annotations" (Findings NAACL 2024)
  - URL: `https://aclanthology.org/2024.findings-naacl.265/`
  - Abstract takeaway: post-editing with external error feedback improves MT metrics; fine-grained feedback helps only when used in a targeted way (`turn10search1`, `turn10search12`).
- Wilken et al., "SubER - A Metric for Automatic Evaluation of Subtitle Quality" (IWSLT 2022)
  - URL: `https://aclanthology.org/2022.iwslt-1.1/`
  - Abstract takeaway: subtitle quality is not only text quality; segmentation and timing matter too (`turn11search0`).
- Matusov et al., "Customizing Neural Machine Translation for Subtitling" (AMTA 2019)
  - URL: `https://aclanthology.org/W19-5209/`
  - Abstract takeaway: subtitle MT quality improves when translation is adapted to subtitling content/style and uses simple inter-sentence context plus subtitle-specific segmentation constraints (`turn12search4`).

### Approach comparison

#### 1. Prompt-only

- Shape in this repo:
  - Replace the current minimal prompt with a subtitle-specific system prompt.
  - Add a compact few-shot block for slang, vocatives, interruptions, and “same line count, return only translations”.
  - Add explicit subtitle style rules: natural spoken Chinese, equivalent profanity strength, consistent punctuation, no censoring, no summaries.
- Benefits:
  - Lowest implementation cost.
  - Directly improves “字幕腔” and dialogue naturalness over the current generic prompt.
  - Keeps current one-pass latency and fail-soft behavior.
- Limitations:
  - Still weak on proper nouns, especially person names, because the model is still guessing from raw chunk text.
  - Term consistency can drift across 60-line chunks because each chunk is independent.
  - JSON safety still depends on obedience if the backend remains free-form chat completions instead of schema-constrained output.
- Judgment:
  - Good baseline cleanup.
  - Not enough alone for this task’s “专名/术语优先” goal.

#### 2. Prompt + light preprocessing

- Shape in this repo:
  - Before translation, build a small chunk-relevant glossary from trusted metadata:
    - `approved_terms`: title zh, franchise/series aliases, organizations/brand names, recurrent in-world terms.
    - `approved_person_names`: only names backed by trusted sources or curated aliases.
    - `locked_original_terms`: names with no trusted zh alias; keep original instead of free-translating.
  - Add narrow context fields without changing the return contract:
    - `previous_lines`
    - `source_lines`
    - `next_lines`
    - ask model to translate only `source_lines`
  - Keep all SRT/ASS structure outside the model, as today.
  - Prefer glossary fields over placeholder replacement unless collisions are proven manageable; placeholders improve enforcement, but they increase subtitle-text surgery risk.
- Why it fits the evidence:
  - Named-entity preprocessing is a proven way to improve translation without changing the core translator (`turn8search1`).
  - Small adjacent context helps consistency and pronoun/dialogue resolution, while full long-range context has diminishing returns (`turn7search0`, `turn12search4`).
  - Subtitle-specific style guidance can sit cleanly beside deterministic term constraints.
- Benefits:
  - Best balance between subtitle naturalness and proper-noun correctness.
  - Works with the repo’s existing line-by-line JSON contract.
  - Does not require a second full model pass for every chunk.
- Risks:
  - TMDB title localization is useful, but TMDB itself documents gaps on person-name localization, so person-name zh still needs a stricter trust model than title zh.
  - Large term tables can crowd the prompt; keep only chunk-relevant items.
  - If source resolution is ambiguous, keeping the original name is safer than forced Chinese output.
- Judgment:
  - Best mainline choice for this task.

#### 3. Prompt + post-check

- Shape in this repo:
  - Translate first.
  - Run a second checker that only verifies hard rules:
    - valid JSON
    - same number of lines
    - approved terms respected
    - unresolved names not freely transliterated
    - cheap style warnings such as obviously wrong punctuation or literal leftovers
  - If flags appear, repair only the flagged lines, not the full chunk.
- Why it helps:
  - Terminology-aware refine flows are supported by WMT 2023 evidence (`turn9search0`).
  - Error-annotation-guided post-editing can improve quality when revision is targeted (`turn10search1`).
- Costs and risks:
  - Running a second creative pass on every chunk doubles latency/cost.
  - Free second-pass rewriting can worsen already-good lines or drift tone/meaning.
  - “Naturalness” alone is hard to verify deterministically; the checker should focus on hard constraints first.
- Judgment:
  - Good as a selective repair path.
  - Bad default for every subtitle chunk in a post-import pipeline that should stay fast and non-blocking.

### Practical pattern set for this task

- Keep subtitle structure outside the model.
  - Current code already does the correct thing by translating only subtitle text and rebuilding SRT/ASS locally.
- Upgrade the payload, not the output shape.
  - Preserve `translations` as the only returned field.
  - Expand the input payload to include:
    - `title_context`
    - `approved_terms`
    - `approved_person_names`
    - `locked_original_terms`
    - `previous_lines`
    - `source_lines`
    - `next_lines`
    - `style_rules`
- Make “trusted alias or keep original” the proper-noun rule.
  - This is stricter than “always Chinese”, but it matches both the task requirement and TMDB’s documented localization gaps for people.
- Make style guidance explicitly subtitle-shaped.
  - Use natural spoken Chinese.
  - Preserve register and interpersonal force.
  - Match profanity severity, not literal wording.
  - Keep questions/questions marks, interruptions, and vocatives alive.
  - Use Chinese punctuation consistently.
- If backend support exists, prefer strict schema output over “JSON only” prompt wording.
  - This is especially valuable because the current code already treats line-count and JSON shape as hard boundaries.
- Reserve post-check for flagged lines.
  - Hard rule failures should trigger repair or retry.
  - Soft naturalness tuning should not become a mandatory second rewrite stage.

### Recommendation

- Recommended mainline: `prompt + light preprocessing`
- Recommended rollout order:
  - 1. Strengthen subtitle-specific prompt and examples.
  - 2. Add approved-term / keep-original preprocessing from trusted metadata.
  - 3. Add a tiny adjacent-line context window.
  - 4. Add post-check only for hard-rule violations or explicitly flagged lines.
- Why:
  - It directly addresses the two user-prioritized problems: proper nouns/terms and natural Chinese subtitle tone.
  - It preserves the repo’s strongest current property: line-safe local reconstruction of SRT/ASS.
  - It avoids making every import slower and more fragile with a universal second-pass rewrite.

## Caveats / Not Found

- `python3 ./.trellis/scripts/task.py current --source` returned `Current task: (none)`, so this note was written to the user-specified task directory rather than an active-session task path.
- This note did not fully rank Wiki / 豆瓣 / Wikidata / TMDB for person-name sourcing. The practical conclusion here is narrower: model-only person-name translation is not reliable enough, and TMDB title localization does not remove the need for a stricter person-name trust policy.
- The current import pipeline does not expose timing-derived reading-speed checks to the translation step, so this research treats subtitle style primarily as wording and punctuation quality, not as full CPS-aware condensation control.
- OpenAI Structured Outputs is a strong fit conceptually, but whether the currently configured OpenAI-compatible backend fully supports strict schema output must be verified during implementation.
