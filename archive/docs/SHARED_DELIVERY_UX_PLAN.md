# docs/SHARED_DELIVERY_UX_PLAN.md (v1)

> 目的：把 `docs/NEXT_STEP.md` 的 `After this step` "shared private-chat 交付体验收口" 主线提前设计到位。
>
> **核心目标**：让 bot 回复在四个渠道里都**舒适、顺眼、有层次**，同时业务真相只维护一套。
>
> 上游决策：`docs/DECISIONS.md` D-032 / D-035。

## 1. 要解决的真实问题

当前所有 bot 回复直接来自业务层常量（`SELECT_USAGE_TEXT` / `CANDIDATE_HEADER` / 各种 `*_FAILED_TEXT`），用法问题有三：

1. **同一条真相在四渠道一字不差**：Telegram 支持富文本、Feishu 支持卡片，但都只拿到裸文本字符串；渠道能力被浪费。
2. **视觉层次缺失**：搜索候选列表、审批提示、状态查询都是一段段短文本，没有标题 / 正文 / 动作的分层，用户扫一眼不容易抓到重点。
3. **错误提示和建议揉在一句**：读起来像"报错+兜售"，不够舒服。

本主线不是加功能，是把"信息传达"做漂亮。**不做 Web UI、不做按钮键盘动画、不做多语言。**

## 2. 设计原则

- **内容模型和渲染分离**：业务层产出结构化 `DeliveryItem`，渠道层决定怎么显示。
- **一致性优先**：同类信息（搜索候选 / 审批 / 状态 / 错误）在所有渠道都是**相同结构**，只是渲染手段不同。
- **简洁优先于华丽**：Emoji 只作为状态标志（✅ / ❌ / ⏳ / ⚠️），不做装饰。
- **中文为主的阅读节奏**：句号 / 冒号 / 破折号用全角；列表用序号或 `·`，不用 `-` 或 `*`。
- **渠道能力梯度**：Telegram > Feishu > personal WeChat ≈ WeCom；纯文本渲染必须始终可用（作为 fallback）。

## 3. 内容模型

统一的 DeliveryItem 抽象：

```python
@dataclass(frozen=True, slots=True)
class DeliveryHeader:
    kind: str              # "search_results" / "approval" / "status" / "error" / "info"
    title: str             # 一级标题
    subtitle: str | None   # 二级副标题（可选）

@dataclass(frozen=True, slots=True)
class DeliverySection:
    label: str | None      # 分组小标题（可选）
    lines: tuple[str, ...] # 内容行（每行自成完整语义）

@dataclass(frozen=True, slots=True)
class DeliveryAction:
    label: str             # 动作描述文案（如 "确认下载"）
    hint: str              # 用户怎么执行（如 "发送：confirm 1" 或 按钮 callback_data）
    kind: str              # "primary" / "secondary" / "destructive"

@dataclass(frozen=True, slots=True)
class DeliveryItem:
    header: DeliveryHeader
    sections: tuple[DeliverySection, ...]
    actions: tuple[DeliveryAction, ...]
    footer: str | None     # 可选：一条额外提示（小字感）
    status: str | None     # "success" / "failure" / "pending" / "warning" / None
```

所有 shared runtime 产出都统一成 `DeliveryItem`。渠道适配层接收 `DeliveryItem` 再渲染。

## 4. 渠道能力矩阵

| 能力 | Telegram | Feishu | personal WeChat | WeCom |
|---|---|---|---|---|
| 富文本（**粗体** / `代码块`） | ✓ MarkdownV2 | ✓ Card / lark_md | — 纯文本 | — 纯文本 |
| 图片 / 文件 | ✓ | ✓ | ✓ (iLink) | — |
| 交互按钮 | ✓ | ✓ | — | — |
| 卡片标题 / 正文分区 | — (靠排版) | ✓ Card element | — | — |
| 消息长度 | 4096 字符 | 较宽松 | 较短 | 较短 |

渲染策略：

- **Telegram**：`DeliveryHeader.title` 渲染为 `*粗体*`；`DeliverySection.label` 渲染为 `_斜体_`；`DeliveryAction.hint` 用 `` `代码块` ``。
- **Feishu**：优先走 `interactive` Card：`header` → card header、`sections` → `div` + `markdown` element、`actions` → `button` element（若 Feishu 允许 private-chat button；否则 fallback 到 text）。webhook / 长连接都走同一个 renderer。
- **personal WeChat**：纯文本 + emoji；`DeliveryHeader.title` 行首加 `【标题】`；`DeliverySection.label` 行首加 `▸ `；动作提示单独一行。
- **WeCom**：纯文本 + emoji；比 WeChat 更保守（不用 `▸`，改 `- ` 前缀；整体更紧凑，因为 callback 被动回包可能被截断）。

## 5. 具体样例：搜索结果

### 5.1 Telegram 渲染（MarkdownV2）

```
*搜索：Dune 2021* ✓

_候选结果（5 条）_
1\. Dune\.2021\.2160p\.UHD\.BluRay\.x265\.10bit\.HDR\.DV\.TrueHD\.7\.1
   ` 25\.3 GB │ ● 1080p │ ↑ 45 `
2\. Dune\.2021\.1080p\.BluRay\.x265\.DDP5\.1
   ` 8\.1 GB │ ● 1080p │ ↑ 120 `
…

*下一步*
发送 `select 1` 开始下载
发送 `search 沙丘 2021` 换关键词
```

### 5.2 personal WeChat 渲染（纯文本）

```
【搜索：Dune 2021】✓

▸ 候选结果（5 条）
1. Dune.2021.2160p.UHD.BluRay.x265.10bit.HDR.DV.TrueHD.7.1
   25.3 GB ｜ 1080p ｜ ↑ 45
2. Dune.2021.1080p.BluRay.x265.DDP5.1
   8.1 GB ｜ 1080p ｜ ↑ 120
…

▸ 下一步
发送 select 1 开始下载
发送 search 沙丘 2021 换关键词
```

### 5.3 Feishu 渲染（Card）

- Card Header：`搜索：Dune 2021`（蓝色 / success 色）
- Section 1：markdown element，内容同 Telegram 版候选列表（`**1.**` 粗体序号）
- Section 2：button element，primary button 文案 `select 1`、secondary `换关键词`

### 5.4 WeCom 渲染（纯文本，被动回包）

```
搜索：Dune 2021 ✓

候选结果（5 条）
- 1. Dune.2021.2160p... | 25.3 GB | 1080p | ↑ 45
- 2. Dune.2021.1080p... | 8.1 GB | 1080p | ↑ 120
…

下一步
- 发送 select 1 开始下载
- 发送 search 沙丘 2021 换关键词
```

## 6. 具体样例：审批提示（下载）

### Telegram

```
*待确认：下载* ⏳

_任务信息_
片名：Dune 2021
来源：Prowlarr / RuTracker
画质：2160p UHD BluRay
大小：25\.3 GB
做种：45

*操作*
✓ 确认下载 → 发送 `confirm 1`
✗ 取消   → 发送 `cancel 1`

_过期时间：10 分钟后_
```

### personal WeChat

```
【待确认：下载】⏳

▸ 任务信息
片名：Dune 2021
来源：Prowlarr / RuTracker
画质：2160p UHD BluRay
大小：25.3 GB
做种：45

▸ 操作
✓ 确认下载  发送 confirm 1
✗ 取消      发送 cancel 1

过期时间：10 分钟后
```

### WeCom / Feishu：类比扩展

## 7. 具体样例：错误（fail-closed）

### 当前 baseline

```
搜索候选状态写入失败，请稍后重试。
```

### 目标 Telegram 渲染

```
*搜索候选状态写入失败* ❌

_原因_
SQLite `candidate_mapping` 写入后立即回读不到刚保存的候选

*建议*
1\. 查看 `logs/trace\.log` 最近一条 `clarification/candidate` 行
2\. 若近期没改 schema，可重发一次搜索；搜索候选在内存里还存在，会再落一次盘
```

错误的"原因 / 建议"一定**分段**，不再揉在一句。

## 8. 状态标志 emoji 用表

| kind | emoji | 用法 |
|---|---|---|
| success | ✓ | Header 尾部 |
| failure | ❌ | Header 尾部；section 独占 |
| pending | ⏳ | Header 尾部；审批提示 |
| warning | ⚠️ | Header 尾部；非阻塞类异常 |
| info | （不加） | 一般通知 |

**禁用的 emoji**：🎬 / 🔥 / ✨ / 🚀 / 💡（装饰性，不传达状态）。

## 9. 分阶段落地

- **Phase 1**：新建 `app/runtime/delivery.py`，只定义 §3 的 dataclass 和四个渠道 `render_*(item)` 函数骨架（只实现纯文本 fallback 版）。写 renderer 的 unit test，覆盖四类 `kind`。
- **Phase 2**：把 `search_media` / `add_to_downloader` / `get_download_status` 的搜索结果 / 审批 / 状态回复改成 `DeliveryItem` 产出；shared runtime 调用对应渠道的 renderer。
  - 不改 `*_FAILED_TEXT` 常量；这些 fail-closed 文本先保持；渐进式迁移。
- **Phase 3**：补 Telegram Markdown 渲染（带 `*粗体*` / `` `代码块` ``）。
- **Phase 4**：补 Feishu Card 渲染。
- **Phase 5**：精调 personal WeChat / WeCom 的纯文本排版（`▸` 前缀、间距、emoji）。
- **Phase 6**：把剩余 `*_FAILED_TEXT` 的错误分类都迁成 `DeliveryItem`（"原因 / 建议" 分段）。

## 10. 可测量退出条件（任一触发即停）

1. `search_results` / `approval` / `status` / `error` 四类核心消息在 Telegram / personal WeChat / Feishu / WeCom 四渠道各有对应 renderer，`.venv/bin/python -m pytest -q tests/test_delivery_renderers.py tests/test_search_media.py tests/test_add_to_downloader.py tests/test_get_download_status.py` 全绿；
2. 或 Phase 1-6 已完成 4 个 Phase，剩余的都属于"再精调排版"（收益递减，停机规则生效）；
3. 或本轮代码变更 < 20 行、只是微调 emoji / 空格（走 `AGENTS.md §11` 停机规则）。

## 11. 不做清单

- 不做 Web UI、桌面端、浏览器预览
- 不做多行内联键盘（Telegram inline keyboard）；只用 callback_data 的 replies，保持"发文本命令"交互形态不变
- 不做动画 / GIF / 表情包
- 不做自定义字体 / 彩色背景
- 不做 i18n；中文主交互
- 不做 A/B 测试框架
- 不收集用户反馈做自动 UX 调参

## 12. 验收：审美通过标准

本主线完成后，以下场景用户在**四个渠道**走一遍：

1. 搜索 `我想看 Dune 2021` → 候选展示
2. `select 1` → 审批提示
3. `confirm 1` → 投递成功 / 失败文案
4. `status <task_ref>` → 状态查询（未完成 / 已完成）
5. `import <task_ref>` → 导入审批
6. 构造一条错误（例如故意让 SQLite 写入失败）→ 错误文案

对比截图：所有渠道的同一信息"一眼能抓到重点"、不拥挤、不乱序，即通过。
