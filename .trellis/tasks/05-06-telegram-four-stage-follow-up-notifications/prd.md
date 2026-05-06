# PRD — Telegram four-stage follow-up notifications

## Goal

将下载完成后的 Telegram 主动通知，从当前“1 条自动导入总结消息”改为“四段式通知”，让操作者能看到后处理推进过程，而不是只在最后收到合并结果。

## Current behavior

- 下载中的 Telegram 卡片会在原消息内实时编辑，这条链路保持不变。
- 下载完成后，后台自动导入当前只主动发送 1 条消息。
- 这 1 条消息会把导入成功、metadata、字幕翻译、媒体库刷新压成一个总结果。

## Required behavior

下载完成后的普通媒体自动导入链，Telegram 主动通知改为固定 4 条：

1. 导入 / 硬链接结果通知
2. 字幕翻译结果通知
3. 媒体库刷新结果通知
4. 最终总结通知

## Explicit scope decisions

- metadata scraping 继续执行，但不单独拆成 1 条主动通知。
- metadata scraping 的结果保留在最终总结内。
- 下载中的 Telegram live progress 原消息编辑链不改。
- 当前改动只收口普通媒体自动导入的主动通知链，不扩到新的渠道专属 UI。

## Delivery contract

- 如果某一阶段被跳过，也要按该阶段发 1 条可读通知，明确说明“跳过”。
- 阶段通知必须按真实执行顺序发送，不能重排。
- 最终总结必须保留 metadata / 字幕 / refresh 三个后处理状态，避免前面分阶段通知后丢失全局视图。
- 失败保持 fail-soft：metadata / 字幕 / refresh 任一失败，不回滚 import success，但必须明确通知失败结果。

## Out of scope

- 不新增 metadata 单独主动通知。
- 不改 Feishu / personal WeChat / WeCom 的展示文案契约。
- 不改 copy-fallback 审批语义。
- 不改 Telegram 下载成功卡片和实时进度条格式。

## Verification

- focused tests 覆盖自动导入阶段通知从 1 条变 4 条。
- focused tests 覆盖导入 / 字幕 / refresh / summary 的顺序和文案来源。
- focused tests 覆盖跳过阶段仍会发通知。
