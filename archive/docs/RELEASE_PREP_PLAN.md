# Release Prep Plan (v7)

> 目的：保留“从质量硬化切到收尾发布准备”这一阶段的历史推进顺序。
>
> 当前定位：**历史归档**。当前保守版发布准备已经完成；本文件不再作为当前入口，继续推进时优先看 `docs/STATUS.md` 与 `docs/NEXT_STEP.md`。

## 1. 当前阶段要解决什么

当前主要缺口不是“代码还没写完”，而是下面 4 件事还没完全收死：

1. `docs/STATUS.md`、`docs/NEXT_STEP.md`、旧入口模板仍残留旧阶段口径
2. 代码里已经落地的能力，还没有明确冻结成“首版发布矩阵”
3. 真实环境状态与业务回归状态还没分开写清
4. 发布前质量 gate 仍主要依赖 compile + pytest，缺少最小 static/lint 收口

## 2. 当前阶段的最小推进顺序

### Phase 1：发布真相对齐

目标：
- 同步 `STATUS` / `NEXT_STEP` / 旧入口模板到当前真实复验结论
- 结束旧的“质量硬化 + webhook 环境边界”口径

本轮最小闭环：
- 文档真相对齐
- 当前阶段蓝图落地
- 旧提示词改写为当前阶段可直接复制版本

### Phase 2：首版发布矩阵冻结

目标：
- 明确“代码里已有实现”与“首版承诺支持”之间的边界

至少要冻结的维度：
- 入口渠道：Telegram / personal WeChat / Feishu / WeCom 哪些纳入首版承诺
- 下载器：Transmission / BT Transmission / qBittorrent 哪些纳入首版承诺
- 媒体后半段：Emby / Jellyfin / Plex 哪些纳入首版承诺
- 真实 smoke：哪些链路必须在发布前具备当前批次证据

输出要求：
- 冻结结果必须写回文档
- 未纳入首版承诺的能力，要明确写成“已实现但当前未纳入发布保证”

当前建议先按下面这版**保守首版矩阵**冻结：

#### 2.1 默认承诺矩阵（首版发布必须守住）

- 入口渠道：Telegram 私聊
- 下载主链：PT Transmission
- 入库与刷新：Emby
- 工作流：movie-first 主链
- 最小闭环：`搜索 -> select -> confirm -> status -> import -> confirm -> refresh`

这部分纳入首版承诺的原因：
- 当前文档长期都把 movie-first 作为最稳场景
- 当前本机真实端口里 `19091 Transmission` 与 `18096 Emby` 可达
- 当前质量入口、主线回归和全量 `pytest` 都已围绕这条主链持续复验

#### 2.2 已实现但当前不纳入首版发布保证

- personal WeChat / Feishu / WeCom 私聊入口
- BT direct split、BT processing path、BT classification、raw_bt 目录选择
- BT subscription scheduler
- qBittorrent 协议路径
- Jellyfin / Plex refresh provider 路径

处理原则：
- 这些能力继续保留在代码和测试里，不回退
- 但在没有当前批次首版证据前，不把它们写成首版发布阻塞项

#### 2.3 当前明确不写入首版承诺的原因

- 当前机器上 `19091` / `18096` / `18098` 已有当轮探针绿灯；`19092` 当前端口监听仍在，但 RPC 探针要继续按当轮结果判断。这只说明**环境可用性要单独记录**，不等于 BT / qB 路径已经自动升级为首版承诺
- qB 测试栈刚补齐 `WEBUI_PORT=18098` 与 `18098:18098` 同步映射；这说明测试栈配置边界已经写清，但仍不该把“今天可达”直接写成“首版必须承诺”
- `docs/TEST_ENV.md` 也已把 Emby 标成当前固定 refresh 入口，把 qB 标成下载器协议辅助实例，并把 Jellyfin / Plex 标成 readiness 评估态
- 这样冻结后，后续发布前 live smoke 就能先集中在最稳主链，不会把“已实现能力”和“本批次必须守住的发布承诺”混在一起

当前状态：
- **Phase 2 已完成**；当前保守首版矩阵已冻结到入口文档与当前阶段文档
- 当前下一步直接进入 **Phase 3：首版矩阵内 live smoke**

### Phase 3：首版矩阵内 live smoke

目标：
- 只围绕首版承诺范围补最小真实闭环证据

优先顺序：
1. 搜索 -> 下载审批 -> confirm -> status
2. 下载完成 -> import 审批 -> confirm -> Emby refresh
3. 首版承诺里的渠道路由入口 smoke

边界：
- 不为未冻结进首版矩阵的能力补发布前证明
- 不把环境不可达写成代码回归

当前状态：
- 已拿到一条真实后半段证据：`status d8f737c1468646c8ab35279fa10f89f89e88428e -> import -> confirm -> Emby refresh` 已成功，目标路径落到 `/data/library/movies/抓住它 Catch It (2015)/...`
- 当前前半段 blocker 已收口到搜索入口：Prowlarr 对 `Catch It 2015`、`抓住它 2015`、`Dune 2021`、`Despicable Me 2 2013`、`卑鄙的我2 2013` 当前都返回 `0` 候选
- 按 2026-04-23 当前操作者确认，这条 Prowlarr blocker 当前优先归因为 NAS 本机网络影响索引器可用性；本阶段先挂起，后续单独回补
- 当前 metadata 现象已确认不阻断主链：`Catch It 2015` 导入时 `TMDB 未命中 title=抓住它, year=2015`，但不回滚 `import.succeeded` 与 `refresh.succeeded`

### Phase 4：发布前质量 gate

目标：
- 在现有 `make quality` / `make verify-mainline` / `make verify-quality-gates` 之上，再补一层最小 static/lint gate

要求：
- 入口要固化到 `Makefile` / CI
- 只加最小、稳定、不会大面积制造噪音的 gate
- 不顺手引入大规模格式化或无关重构

当前状态：
- **Phase 4 已完成**
- `make quality` 当前已升级为 `compile + pyflakes + docs/tests`
- `make verify-mainline`、`make verify-quality-gates` 当前都已复验通过

## 3. 当前阶段明确不做什么

- 不继续追三座大山行数
- 不新增用户可感知功能
- 不扩协议
- 不恢复“继续推进完整度”主线
- 不把 BT / qB / Jellyfin / Plex 全部一次性抬成首版承诺
- 不为了凑发布口径去删除现有能力或降级已通过测试

## 4. 当前阶段的退出条件

当以下条件同时满足时，可宣告“首版发布准备完成”：

1. 当前文档真相与当前验证真相一致
2. 首版发布矩阵已冻结
3. 首版矩阵内最小 live smoke 已补齐
4. 发布前质量 gate 已收口
5. 默认分支现有回归与 focused tests 不回退

## 5. 当前建议

- Phase 1 与 Phase 2 当前都已完成
- Phase 3 与 Phase 4 当前都已完成
- 当前保守版发布准备已可宣告完成
- 后续若继续，只在 NAS 网络恢复后单独回补 Prowlarr 前半段搜索 smoke；否则不再继续扩大默认分支主线
