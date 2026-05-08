# add automatic subtitle sync via ffsubsync

## Goal

为字幕后处理链默认接入 `ffsubsync` 自动同步：先对源英文字幕做自动对齐，再沿用同步后的时间轴生成 plain `.zh.srt`，并基于它重生成 `.dual.ass`。目标是把“当前人工观察到的整体慢半拍/快半拍和轻度线性漂移”收口进默认主链，而不引入 Whisper/ASR 这类重型方案。

## What I already know

* 上一轮已经把字幕翻译链路收口为正式能力：断点续跑、chunk 进度状态、ASS 字号可配。
* 当前 plain `.zh.srt` 和 `.dual.ass` 都沿用原字幕时间轴；翻译本身不改 timing。
* 当前 `app/services/subtitle_translation_support.py` 里只有 SRT->ASS 时间码格式转换，没有任何自动同步逻辑。
* 自动同步方案调研已完成：`ffsubsync` 更适合作为第一批默认接入路线；`alass` 能力更强但依赖/许可证风险更高；Whisper/ASR 路线明显超出当前任务范围。
* Research 结论明确建议：自动同步不要直接分别改最终 `.zh.srt` / `.dual.ass`，而是先同步源英文字幕，再用同步后的时间轴生成两个产物。

## Assumptions (temporary)

* `ffsubsync` 作为外部同步器是可接受的新依赖/运行时前置。
* MVP 应该同时覆盖 `.zh.srt` 和 `.dual.ass`，但主真相文件应是 plain `.zh.srt`。

## Open Questions

* 当前无阻塞开放问题；已决定第一版只接未来的新翻译主链，不覆盖已入库旧字幕的重校时。

## Requirements (evolving)

* 在字幕后处理主链中默认接入 `ffsubsync`。
* 第一版只作用于未来的新翻译主链，不新增“对已存在库内字幕重新校时”的批处理入口。
* 自动同步必须先作用于源英文字幕或其时间轴真相，再生成：
  * plain `.zh.srt`
  * `.dual.ass`
* plain `.zh.srt` 仍是时间轴真相；`.dual.ass` 必须基于同步后的 plain 时间轴重生成，而不是单独再跑一次同步。
* 同步失败必须 fail-soft：
  * plain 翻译结果仍可生成
  * `.dual.ass` 仍可按原时间轴生成
  * 失败原因可观察
* 不引入 Whisper/ASR、波形分析或多段智能时间轴重建。
* 不把自动同步逻辑混进 chunk 翻译 prompt / provider 请求。

## Acceptance Criteria (evolving)

* [ ] 字幕后处理主链默认支持 `ffsubsync` 自动同步
* [ ] `.zh.srt` 与 `.dual.ass` 共享同一份同步后时间轴
* [ ] 自动同步失败时仍保持 fail-soft，不拖垮现有字幕翻译主链
* [ ] 相关测试覆盖同步成功/失败与 fallback 路径
* [ ] 不影响现有字幕翻译主链与主线 gate

## Definition of Done (team quality bar)

* 相关测试更新并通过
* `make lint`、`make quality`、`make verify-mainline` 继续通过
* 不引入自动音频对齐 / ASR / 新依赖

## Out of Scope (explicit)

* Whisper/ASR 驱动的自动同步
* `alass` / `Subaligner` 等第二同步器并行接入
* 多段非线性时间轴修复策略切换
* 字幕文本内容重译
* 已入库旧字幕的重校时批处理入口

## Technical Notes

* 相关 spec：
  * `.trellis/spec/backend/index.md`
  * `.trellis/spec/backend/subtitle-translation-contracts.md`
  * `.trellis/spec/backend/quality-guidelines.md`
* 相关历史任务：
  * `.trellis/tasks/archive/2026-05/05-08-subtitle-translation-proxy/`
* 现有关键代码：
  * `app/services/subtitle_translation_support.py`
  * `app/services/subtitle_translator.py`
* 相关 research：
  * `.trellis/tasks/05-08-subtitle-offset-timing/research/auto-subtitle-sync-options.md`
