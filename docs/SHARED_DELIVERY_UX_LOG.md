# Shared delivery UX log (v1)

> 目的：承接当前“shared private-chat 交付体验收口”主线的详细台账。
> 约束：蓝图看 `docs/SHARED_DELIVERY_UX_PLAN.md`；`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 当前主线状态：2026-04-19 已完成；通过 `.venv/bin/python -m pytest -q tests/test_delivery_renderers.py tests/test_search_media.py tests/test_add_to_downloader.py tests/test_get_download_status.py` 得到 `198 passed`，满足 `Done when` 第 1 条后已切到 `docs/QUICK_START_PLAN.md`
- 上一条已完成主线“`series / anime` 独立名称解析最小实现”已在 2026-04-19 通过 `_extract_title_year_for_scrape()` 接入统一 parser 满足 `Done when` 第 1 条，focused suite `245 passed`
- 当前这一步的设计蓝图、Phase 顺序和退出条件统一看 `docs/SHARED_DELIVERY_UX_PLAN.md`

## 2. Risk groups

### 2.1 DeliveryItem 抽象

已完成闭环：
- 已新增 `app/runtime/delivery.py`，落下 `DeliveryHeader` / `DeliverySection` / `DeliveryAction` / `DeliveryItem` 四个 dataclass，以及 Telegram / Feishu / personal WeChat / WeCom 四个纯文本 fallback renderer 骨架。
- 已把 `search_media` 成功候选回复接到 `DeliveryItem`：shared runtime 现在会按 `channel` 选择 Telegram / Feishu / personal WeChat / WeCom 文本 renderer，搜索结果不再只复用同一份裸字符串。
- 已新增 `tests/test_delivery_renderers.py`，先锁 `search_results` / `approval` / `status` / `error` 四类核心消息在四渠道 fallback 渲染的最小排版输出。

当前风险：
- shared runtime 和 service 现在仍主要直接返回字符串；虽然 `DeliveryItem` 与 renderer 骨架已落地，但还没真正接进搜索、审批、状态主链。

### 2.2 四渠道 renderer

已完成闭环：
- 已把 `add_to_downloader` 的待确认下载回复接到 `DeliveryItem`：shared runtime 在序号选片后会按 `channel` 输出分层审批提示，保留原有 approval / jobs / SQLite 真相和 fail-closed 文本常量不变。
- 已把 `get_download_status` 的成功状态回复接到 `DeliveryItem`：shared runtime 现在会按 `channel` 输出状态摘要和后续处理分区，下载状态持久化与自动导入跟进逻辑不变。

当前风险：
- Telegram / personal WeChat / Feishu / WeCom 还没有按同一内容模型分开的 renderer；渠道差异目前主要靠裸文本常量承接。

### 2.3 错误与动作分层

当前风险：
- 剩余 fail-closed 错误文本还没接到 `DeliveryItem`；失败原因、处理建议和下一步动作仍经常揉在同一段字符串里。

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_delivery_renderers.py tests/test_search_media.py tests/test_add_to_downloader.py tests/test_get_download_status.py`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 新闭环优先按 2.1~2.3 合并；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 当前主线完成后，在 `docs/NEXT_STEP.md`、`docs/STATUS.md`、`README.md` 和 `AGENTS.md` 同步切到下一项。
