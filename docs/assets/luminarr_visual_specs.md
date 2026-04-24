# Luminarr 视觉素材说明

这份文件是给后续图片生成直接使用的工作区规格，不是项目真相文档。

当前计划生成 6 张图：

1. `docs/assets/luminarr-architecture-overview.png`
   目的：一张图讲清项目结构
   重点：四渠道入口 -> shared runtime -> services -> clients/db -> 外部系统
   风格：信息图 + 产品架构海报，中文标题，少量英文技术标签

2. `docs/assets/luminarr-interaction-montage.png`
   目的：展示“用户最终如何互动”
   重点：用户在四渠道私聊里发一句话，系统返回搜索卡片 / 待确认卡片 / 状态卡片
   风格：产品宣传图，带消息界面拼贴感

3. `docs/assets/luminarr-card-telegram.png`
   目的：Telegram 消息卡片效果图
   重点：接近当前文本交互风格，蓝白 Telegram 气质，清晰的搜索结果卡片

4. `docs/assets/luminarr-card-personal-wechat.png`
   目的：personal WeChat 消息卡片效果图
   重点：更生活化、简洁、偏绿色，保留私聊工具感

5. `docs/assets/luminarr-card-feishu.png`
   目的：Feishu 消息卡片效果图
   重点：更偏工作协作工具，块面清晰，层级分明

6. `docs/assets/luminarr-card-wecom.png`
   目的：WeCom 消息卡片效果图
   重点：企业工具风格，稳重、规整、偏蓝灰

统一要求：

- 画面语言统一，但每个渠道要有自己的 UI 气质
- 不做黑底赛博风，不做泛紫色 AI 海报
- 所有图都以“产品说明 / 项目介绍”用途为目标，不是纯艺术海报
- 中文为主，允许少量英文技术标签
- 不要出现不存在的功能，例如 Web UI、按钮审批、复杂图表后台
- 必须符合当前项目真相：
  - 四渠道私聊入口：Telegram / personal WeChat / Feishu / WeCom
  - shared runtime
  - services / clients / SQLite
  - 主链：搜索 -> 下载审批 -> 导入审批 -> 刷新

推荐生成顺序：

1. 先出 `luminarr-architecture-overview.png`
2. 再出 `luminarr-interaction-montage.png`
3. 最后出 4 张渠道卡片图
