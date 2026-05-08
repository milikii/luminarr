# harden subtitle translation pipeline

## Goal

把当前“能翻样本、整片易中断”的字幕翻译链路收口成正式可恢复能力：先实现断点续跑、chunk 进度持久化 / 日志、ASS 字号可配置，再重跑《爱的进行时 (2015)`/`Akron` 的整片字幕翻译，确认能把正式中文字幕落到媒体库并刷新 Emby。

## What I already know

* 当前 `.env` 中字幕翻译代理开关已经打开；我们已经试过多组 provider/model。
* 样本字幕在某些 provider 组合下可以成功翻译，但整片翻译会因为 timeout、503、502、连接断开等上游不稳定而中断。
* 现有代码对单块失败是 fail-fast：一旦某个 chunk 最终失败，整片结果不会落盘，也无法从成功 chunk 继续。
* 当前双语 ASS 字号是硬编码的：中文 `44`、英文 `24`，对实际观感偏小。
* 当前媒体库目录 `/data/library/movies/爱的进行时 (2015)/` 仍然只有原始 `.srt`，没有正式 `爱的进行时 (2015).zh.srt`，所以 Emby 刷新也不会显示中文字幕。
* 基于 OSS 调研，最值得优先借鉴的是：断点续跑、chunk 进度持久化、严格一对一映射、可观察日志。

## Requirements

* 保持字幕翻译链路继续走当前 `.env` 里的 provider / model / proxy 运行时配置，不额外硬编码到代码里。
* 在业务代码里为整片翻译增加断点续跑能力：
  * chunk 成功后落盘进度
  * 中断后从最后成功 chunk 继续
* 增加 chunk 级可观察性：
  * 至少能记录当前 chunk 索引、重试次数、失败原因
* 保持当前严格的一对一映射约束：
  * 输入行数与输出行数必须一致
  * 时间轴仍继承原字幕，不在本轮做校时逻辑
* 把双语 ASS 字号做成可配置，而不是硬编码常量。
* 若可行，直接把 `爱的进行时 (2015).zh.srt` 和 `爱的进行时 (2015).dual.ass` 落到媒体库目录。
* 成功后触发一次 Emby 刷新。
* 如果整片翻译仍失败，必须明确记录失败点，并保留可恢复进度，不要再次从头开始。

## Acceptance Criteria

* [ ] 字幕翻译链路支持断点续跑，而不是单块失败整片作废
* [ ] chunk 进度与失败原因可观察
* [ ] ASS 中英文字号改成可配置
* [ ] 至少完成一次真实整片字幕翻译重试，并记录结果
* [ ] 若翻译成功，媒体库目录中出现 `爱的进行时 (2015).zh.srt`
* [ ] 若翻译成功，已执行 Emby refresh
* [ ] 相关测试更新并通过

## Out of Scope

* 自动音频对齐、语音识别、ASR 重建时间轴
* 固定 offset 校时功能
* 多 provider/key 池自动切换
* 与字幕翻译无关的导入、metadata、Emby 刷新链路重构

## Technical Notes

* 相关 spec：
  * `.trellis/spec/backend/index.md`
  * `.trellis/spec/backend/subtitle-translation-contracts.md`
  * `.trellis/spec/backend/quality-guidelines.md`
* 相关 research：
  * `.trellis/tasks/05-08-subtitle-translation-proxy/research/oss-llm-subtitle-translation-patterns.md`
* 当前最小实现顺序：
  1. 断点续跑 / 进度状态
  2. chunk 日志
  3. ASS 字号配置
  4. 真实整片回归
