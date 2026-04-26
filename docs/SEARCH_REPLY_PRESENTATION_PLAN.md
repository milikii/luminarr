# docs/SEARCH_REPLY_PRESENTATION_PLAN.md (v1)

> 目的：把“电影 / PT 搜索结果 + BT 只读结果”的展示体验增强主线先定义清楚，作为当前质量硬化之后的后续候选主线。
>
> 当前定位：这不是当前执行主线；当前唯一施工真相仍看 `docs/NEXT_STEP.md`。旧的 shared delivery 蓝图继续保留在 `archive/docs/SHARED_DELIVERY_UX_PLAN.md` 作为历史参考。

## 1. 要解决的真实问题

- 当前功能真相是对的，但最终回包仍更像系统日志，不像“适合长期私聊使用”的消息：
  - PT 搜索结果虽然已进入 `DeliveryItem`，但仍是纯文本分段，`海报：暂未接入图片` 直接暴露给用户。
  - `bt搜` / `bt批量` 仍是逐行文本拼接，缺少图、层级和更明确的视觉焦点。
  - Telegram 已有最小图片发送能力，但只服务 personal WeChat 登录二维码，没有接到搜索结果展示。
- 这条主线服务的是“更好看、更顺眼、更像成品消息”的用户价值，不改 workflow、安全边界或下载行为。

## 2. 固定边界

- 当前阶段不改 `docs/NEXT_STEP.md`；这份文档只定义后续显式切线后的施工顺序。
- 只覆盖三类消息：
  - 电影 / PT 搜索结果
  - `bt搜` 只读结果
  - `bt批量` 预览结果
- 不在同一轮混入：
  - 审批、状态、导入、cleanup 富媒体化
  - shared runtime / approval / `jobs` / lease / dispatch 真相变更
  - 自动下载、自动确认、helper 放宽成写真相
  - 登录态站点、CAPTCHA、浏览器自动化

## 3. 目标体验

- **Telegram first**
  - 首个 richer reply 渠道固定为 Telegram。
  - 目标形态是“海报 / 封面 + 更清晰 caption 层级 + 克制的符号体系 + 现有文本命令提示”。
  - 交互命令仍保持 `select 1`、`search xxx`、`bt批量 1-3` 这类现有文本协议，不把这条主线扩成新按钮协议。
- **其他渠道首阶段文本降级**
  - Feishu / personal WeChat / WeCom 首阶段先复用同一展示模型，输出更整洁的纯文本。
  - 这些渠道首阶段不承诺“同样带图”，避免把 Telegram richer reply 阻塞成四渠道并行大工程。
- **符号体系**
  - 允许少量语义符号服务分层，例如搜索、海报、只读说明、下一步。
  - 不靠堆 emoji 制造“好看”，避免回到表情包式噪声。

## 4. 图源与展示策略

### 4.1 电影 / PT 搜索结果

- 海报来源固定为**搜索阶段的只读在线图源**，不依赖导入后本地 sidecar。
- 允许复用现有 TMDB 命中与 Fanart poster URL 能力；若 TMDB 已命中但拿不到 poster，则优雅降级为无图 caption，不显示“暂未接入图片”这类实现细节文案。

### 4.2 成人 BT 只读结果

- 目标态定义为：**尽量全量带图**。
- 但施工必须分阶段：
  1. **Phase A**：先做 exact-id 与稳定只读图源，例如 `SSIS-123` 这类可稳定命中的结果；图源字段只服务展示。
  2. **Phase B**：在不放宽真相边界的前提下，继续补泛关键词 / 泛候选结果的只读图源覆盖。
  3. **Phase C**：若仍有明显价值，再评估更多稳定公开图源；无稳定映射时继续纯文本降级。
- 任何阶段都必须满足：
  - 图贴错比没图更差；不稳定就不用图。
  - 图源字段不写入 `candidate_mapping`、approval、`jobs`、lease 或 downloader dispatch 真相。
  - exact-id helper 仍保持 BT-only、read-only，不借展示层扩成自动下载入口。

## 5. 计划中的接口变化

- 展示模型后续要支持“图 + 文”统一表达；当前 `DeliveryItem` 需要预留可选 poster / media 描述，而不是继续把“海报”塞进普通文本行。
- Telegram 发送层后续要支持：
  - `parse_mode`
  - richer caption
  - 远程图片或经下载后的本地图片发送
- 成人只读 helper 后续允许补 display-only 字段，例如：
  - `cover_url`
  - `detail_url`
  - `source_site`
  但这些字段只属于展示层，不进入审批或下载真相。

## 6. Phase 顺序

1. 冻结这份蓝图，明确边界、验收场景与非目标。
2. Telegram 电影 / PT 搜索结果先接海报与更清晰 caption。
3. Telegram 成人 BT exact-id 只读结果补稳定封面。
4. 成人 BT 从 exact-id 向“尽量全量带图”扩面，但始终允许安全降级。
5. Feishu / personal WeChat / WeCom 首阶段只补共享文本排版，不和 Telegram richer reply 绑死。

## 7. 验收场景

- `我想看 Dune 2021`
  - Telegram 返回海报 + 分层候选结果 + 现有文本命令提示。
  - 其他渠道仍可读、顺眼，不回退成更乱的日志块。
- `bt搜 SSIS-123`
  - Telegram 在 exact-id 命中时返回封面 + 番号 / 分类 / 历史提示。
  - 若图源失败，仍保持 helper 文本与历史提示，不影响只读真相。
- 泛关键词成人查询
  - 有稳定图源时显示图。
  - 无稳定图源时明确降级为纯文本，不误贴无关封面。

## 8. 明确不做

- 不把这条主线扩成 Web UI / 桌面端 / 浏览器预览。
- 不把“更好看”当成理由去改审批协议、下载器路由或导入后半段。
- 不把 adult image 覆盖目标写成“首轮必须全部实现”；首轮先锁 Telegram-first 与 phased-image 边界。
