# Subtitle Provider Smoke Tool

## Goal

为字幕 provider/model 切换提供一个固定、可复验的自检入口，操作者可以通过 `python -m ...` 和固定 `make` target 快速确认当前字幕翻译配置是否可用、provider 是否接受当前 model、以及最小真实字幕翻译链是否能跑通。

## What I already know

* 用户要求新增 `app/maintenance/verify_subtitle_provider_smoke.py`，并更新 `Makefile`、`tests/test_makefile.py`，必要时新增单测文件。
* 当前字幕翻译主链由 `app.services.subtitle_translator.SubtitleTranslatorService` 和 `app.services.subtitle_translation_support` 提供，实际请求走 OpenAI-compatible `/chat/completions`。
* 启动装配会把 `subtitle_translation_api_key/base_url/model/timeout_seconds` 与 `settings.outbound_proxy_url` 一起注入 `SubtitleTranslatorService`。
* `app/maintenance/` 现有脚本风格是 `python -m` 入口、`argparse` + `main(argv)` 返回退出码、通过单测直接调用 `main(...)` 验证。
* `Makefile` 现有 contract 通过 `tests/test_makefile.py` 保护 target 名称、help 文案和具体命令。

## Assumptions (temporary)

* 这次只新增维护/自检工具，不修改导入主链和字幕翻译业务逻辑。
* `/models` 检查只作为辅助验证；provider 不支持、返回体不可解析或接口约定不一致时，只记 warning，不单独阻断整个自检。
* 最小真实翻译链可以直接复用 `SubtitleTranslatorService` 的实际请求路径，并使用内置字幕样例行触发一次真实 chat completion。

## Open Questions

* 无阻断问题；按当前用户要求直接实现。

## Requirements

* 提供 `python -m app.maintenance.verify_subtitle_provider_smoke` 入口。
* 提供固定 `Makefile` target 指向该模块。
* 自检输出至少包含当前字幕 provider 配置摘要：
  * `base_url`
  * `model`
  * 当前请求是直连还是通过 `OUTBOUND_PROXY_URL`
* 自检尝试请求 provider 的 `/models`：
  * 请求成功时，校验当前 `model` 存在于 provider 返回的模型列表。
  * provider 不支持该接口、HTTP 语义不兼容或返回体无法可靠解析时，输出 warning，但继续执行后续翻译链检查。
* 自检用内置英文字幕样例跑一次最小真实翻译链：
  * 复用现有 `SubtitleTranslatorService`、settings 和 `httpx` 约定
  * 验证返回的译文数量与 `source_lines` 等长
  * 验证每一行译文都是非空字符串
* 成功时输出清晰摘要并返回 `0`。
* 失败时输出明确原因并返回非零退出码。
* 先补 failing tests，再实现。

## Acceptance Criteria

* [ ] `tests/test_makefile.py` 先新增针对新 target/help 文案的失败断言。
* [ ] 新增 `tests/test_verify_subtitle_provider_smoke.py`，先覆盖成功、warning 继续、模型缺失失败、译文校验失败等关键路径并先失败。
* [ ] `app/maintenance/verify_subtitle_provider_smoke.py` 实现后，上述测试转绿。
* [ ] 自检脚本默认不会泄露 API key 等敏感值。
* [ ] 业务主链逻辑无行为变更。

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* 不新增第二套字幕 provider SDK / client。
* 不修改 `SubtitleTranslatorService` 的业务职责和导入时行为。
* 不扩展为通用模型探活平台或 UI 页面。

## Technical Notes

* 相关实现：
  * `app/services/subtitle_translator.py`
  * `app/services/subtitle_translation_support.py`
  * `app/config.py`
  * `app/main.py`
* 相关 spec：
  * `.trellis/spec/backend/subtitle-translation-contracts.md`
  * `.trellis/spec/backend/quality-guidelines.md`
