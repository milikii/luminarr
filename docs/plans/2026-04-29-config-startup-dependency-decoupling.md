<!-- /autoplan restore point: /tmp/main-autoplan-restore-20260429-002309.md -->
# Config Startup Dependency Decoupling Plan

生成时间：2026-04-29  
分支：`main`  
状态：FINALIZED  
审定结论：采用方案 A  
来源：`docs/NEXT_STEP.md`、`docs/TASKS.md`、`docs/STATUS.md`、当前代码真相

## 1. Final Decision

本轮不做“无 Telegram token 也能启动”。

本轮只做两件事：

1. 把 `PROWLARR_*` 和 legacy `TRANSMISSION_BASE_URL` 从“全局启动硬必填”收口成“按真实能力判定”。
2. 把这套能力边界同时落到配置校验、启动装配、运行时 fail-closed、focused tests、操作文档里。

`TELEGRAM_BOT_TOKEN` 继续保持当前宿主必填。若后续要放开，单独进入下一条 `telegram_sidecar_runtime.py` 宿主解耦主线。

## 2. Why This Scope

当前真正的问题不是“少几个 required 字段”，而是“能力真相分裂”：

- `load_settings()` 把几项依赖写死成全局必填
- `main()` 仍无条件装配 Telegram / Prowlarr / legacy Transmission
- 文档和 `.env.example` 继续把这些依赖描述成统一必填

如果只改 `config.py`，不改装配和运行时 guard，就会得到“启动变绿，第一次调用才炸”的假解耦。

因此，这轮的交付必须是一个小而完整的 capability contract，而不是单点条件判断补丁。

## 3. User-Facing Promise

这轮完成后，用户至少应获得两个明确结果：

1. `qBittorrent-only` 或 `DOWNLOADER_INSTANCES` 多实例场景，不再因为缺少 legacy `TRANSMISSION_BASE_URL` 而启动失败。
2. 缺少 `Prowlarr` 时，direct magnet / `status` / `import` / `cleanup` 仍可启动；搜索类能力给出 1 条明确 unavailable 说明，而不是启动崩溃或堆栈异常。

## 4. Implementation Alternatives

### Approach A: Capability Contract 收口

- 摘要：保留 Telegram-first 宿主，只把 `Prowlarr` 和 legacy `Transmission` 校验改成按能力判定，并让装配、运行时 guard、测试和文档同步。
- 工作量：M
- 风险：中
- 优点：
  - 命中当前真实痛点，diff 可控
  - 不触碰宿主生命周期，不会和下一条主线打架
  - 能把“启动绿但运行时红”的风险一起收掉
- 缺点：
  - 还不能实现 non-Telegram 独立启动
  - 需要把若干 legacy fallback 显式化

### Approach B: 直接做宿主解耦

- 摘要：本轮直接把 Telegram 从唯一宿主降级为一个可选入口，让非 Telegram runtime 可独立启动。
- 工作量：L
- 风险：高
- 优点：
  - 一次性解决 `TELEGRAM_BOT_TOKEN` 必填争议
  - 产品边界最干净
- 缺点：
  - 已超出当前主线
  - 会同时触碰 sidecar 生命周期、运行入口、渠道装配和 smoke 体系

### Approach C: 只改文档，不改行为

- 摘要：承认当前就是 Telegram/Prowlarr/Transmission-first，把现状正式写成产品边界。
- 工作量：S
- 风险：低
- 优点：
  - 最便宜
  - 没有回归风险
- 缺点：
  - 不能解决 qB-only 和 non-search 启动阻断
  - 会把现有工程债继续前推

**推荐：Approach A。**  
原因：它是当前唯一既解决用户真实阻断、又不提前踩进宿主解耦主线的方案。

## 5. Premise Decision

### 锁定前提

- 当前产品仍是 `Telegram-first` 宿主，`TELEGRAM_BOT_TOKEN` 本轮继续必填。
- “non-Telegram 独立运行”仍是下一条主线，不在这轮偷渡实现。
- 本轮必须允许“部分能力可启动但不可用”，前提是 unavailable 反馈明确且 focused tests 覆盖。

### 被拒绝的前提

- 不接受“先把 `TELEGRAM_BOT_TOKEN` 放开，宿主以后再说”。
  原因：`app/main.py` 当前无条件 `build_application(settings.telegram_bot_token)` 并 `run_polling()`，先放宽校验只会制造假绿灯。

## 6. What Already Exists

- `app/config.py` 已经集中负责 env 解析和规范化。
- `DOWNLOADER_INSTANCES`、`PT_DOWNLOADER`、`BT_DOWNLOADER` 已经能表达多下载器实例与角色绑定。
- `app/main.py` 已经同时支持 Transmission 和 qBittorrent client 装配。
- shared private-chat runtime、approval、download monitor、import、cleanup 主链都已存在。
- 项目内已经有大量 “service not ready / config missing / fail-closed” 文本协议，可复用同类模式。

## 7. Current Hard Boundaries

- `load_settings()` 当前无条件要求 `TELEGRAM_BOT_TOKEN`、`PROWLARR_*`、`TRANSMISSION_BASE_URL`。
- `main()` 当前无条件构建：
  - Telegram `Application`
  - `ProwlarrClient`
  - `SearchMediaService(search_func=prowlarr_client.search)`
  - `ManageBtSubscriptionService(search_func=bt_source_adapter.search)`
  - legacy `TransmissionClient`
- `_resolve_downloader_client_for_dispatch()` 当前在 `downloader_name=""` 时直接回退到 legacy Transmission client。
- `.env.example` 和 `docs/GETTING_STARTED.md` 仍把 `TRANSMISSION_BASE_URL` 写成多实例场景下也不可省略。

## 8. Capability Contract

| 能力 | 本轮启动要求 | 缺失时行为 |
| --- | --- | --- |
| Telegram 宿主启动 | `TELEGRAM_BOT_TOKEN` | 启动硬失败 |
| PT / 自然语言搜索 | `PROWLARR_BASE_URL` + `PROWLARR_API_KEY` | 运行时显式 unavailable |
| BT 订阅搜索链 | 至少 1 个可用 BT 搜索 provider；本轮默认先覆盖 `Prowlarr` 缺失场景 | 运行时显式 unavailable |
| BT 只读 / direct magnet / `status` / `import` / `cleanup` | 不依赖 `Prowlarr`；依赖对应 downloader/job 真相 | 保持可启动；缺具体依赖时按既有 fail-closed 文本返回 |
| 下载器投递 | 至少 1 条可投递路径：legacy Transmission 或有效 `DOWNLOADER_INSTANCES` + role binding | 启动硬失败或运行时显式 config missing，不能静默回退 |

补充要求：

- 本轮要把 “legacy Transmission fallback” 定义清楚。
- 若 `DOWNLOADER_INSTANCES` 已存在且 caller 应携带 `downloader_name`，空名回退不能再默默吃到 legacy Transmission。

## 9. Architecture Shape

```text
.env
  |
  v
load_settings()
  |
  +--> host capability
  +--> search capability
  +--> downloader capability
  |
  v
main() wiring
  |
  +--> construct only the clients/services the capability contract allows
  |
  v
runtime guards
  |
  +--> available: run normal flow
  +--> unavailable: explicit fail-closed reply
  |
  v
focused tests + operator docs
```

## 10. Execution Plan

### Task 1: Freeze the Capability Matrix

- 先把“命令 / 链路 -> 依赖 -> 缺失时行为”列表固定下来。
- 至少覆盖：
  - Telegram host startup
  - 自然语言搜索
  - BT 只读
  - `btsub run`
  - direct magnet
  - `status`
  - `import`
  - `cleanup`

### Task 2: Conditional Config Validation

- `TELEGRAM_BOT_TOKEN` 继续保留必填。
- `PROWLARR_*` 不再全局必填，改为由搜索能力决定。
- `TRANSMISSION_BASE_URL` 不再在“已有有效 downloader instances”场景下全局必填。
- 需要新增或收口 capability-aware 校验 helper，避免把判断散落在 `load_settings()` 返回处。

### Task 3: Startup Wiring Must Match Validation

- 缺 `Prowlarr` 时，`main()` 不能再无条件构建 `ProwlarrClient` 并注入必须依赖它的 service 路径。
- 缺 legacy `TRANSMISSION_BASE_URL` 但已有有效 downloader instances 时，`main()` 仍应完成下载器装配。
- 要明确 empty `downloader_name` 的 legacy fallback 规则，避免 qB-only 启动后第一次下载才炸。

### Task 4: Runtime Fail-Closed Guards

- 搜索类入口缺依赖时返回统一的明确 unavailable 文本。
- `btsub` 缺搜索 provider 时返回明确 unavailable 文本。
- direct magnet / `status` / `import` / `cleanup` 继续走现有 fail-closed 协议，不因为缺 `Prowlarr` 误伤。

### Task 5: Focused Verification

- 增加 config focused tests。
- 增加 main/runtime focused tests。
- 维持仓库当前主线验证入口不回归。

### Task 6: Operator Truth Sync

- 更新 `.env.example`。
- 更新 `docs/GETTING_STARTED.md`。
- 更新 `docs/STATUS.md`、`docs/NEXT_STEP.md`、`docs/TASKS.md` 的当前主线描述。

## 11. Focused Test Matrix

| 场景 | 预期 |
| --- | --- |
| 仅 Telegram + legacy Transmission + Prowlarr | 继续正常启动 |
| Telegram + qB-only `DOWNLOADER_INSTANCES`，无 legacy `TRANSMISSION_BASE_URL` | 启动成功 |
| Telegram + 无 `Prowlarr`，但 direct magnet / `status` / `import` / `cleanup` 相关依赖齐全 | 启动成功 |
| Telegram + 无 `Prowlarr`，执行搜索类入口 | 显式 unavailable |
| 无 `TELEGRAM_BOT_TOKEN` | 本轮仍为启动硬失败 |
| 无任何可投递 downloader 能力 | fail-closed，不能假启动 |

## 12. Files In Scope

- `app/config.py`
- `app/main.py`
- `tests/test_config.py`
- `tests/test_main.py`
- 必要的 runtime focused tests
- `.env.example`
- `docs/GETTING_STARTED.md`
- `docs/STATUS.md`
- `docs/NEXT_STEP.md`
- `docs/TASKS.md`

## 13. NOT in Scope

- 不做 `telegram_sidecar_runtime.py` 宿主解耦
- 不做 non-Telegram 独立启动
- 不改 SQLite schema
- 不改 BT/PT 主链语义、审批边界、`ExecutionGate`
- 不顺手收口大 service 文件
- 不重做部署拓扑或配置格式

## 14. Main Risks

1. 把校验放宽了，但 `main()` 仍无条件装配依赖，造成假绿灯。
2. 把 `TRANSMISSION_BASE_URL` 去掉后，empty `downloader_name` 仍走 legacy fallback，造成首次下载才暴露配置洞。
3. 把 `Prowlarr` 放成可选后，没有统一 unavailable 协议，导致搜索类入口体验漂移。

## 15. Done When

1. `load_settings()` 不再无条件硬要求 `PROWLARR_*` 和 legacy `TRANSMISSION_BASE_URL`。
2. `TELEGRAM_BOT_TOKEN` 在本轮继续作为当前宿主必填，并在文档与测试里写清。
3. `main()` 的装配方式与 capability contract 一致。
4. 搜索类能力缺依赖时是显式 fail-closed，不是启动崩溃或隐式异常。
5. qB-only / multi-downloader 启动矩阵有 focused tests。
6. `make quality`、`make verify-mainline`、`make verify-adult-bt-wedge` 通过。

## 16. After This Step

1. 若还要支持无 Telegram token 启动，下一条主线切 `app/bot/telegram_sidecar_runtime.py` 宿主解耦。
2. 若这轮暴露 legacy downloader fallback 更深层耦合，再单开 downloader host contract 子问题，不混入宿主解耦。
