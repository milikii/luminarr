# 实施上下文

## 当前边界

- `成人搜` 已经修到 adult-only fallback 正常返回资源。
- 当前 Telegram 运行是 `Telegram-only + 192.168.2.106:10808` 代理的临时运行态，用于真实 smoke。
- 这轮新主线不应回退 `adult-only`、`不进 PT`、`不扩未配置来源` 这些约束。

## 优先级顺序

1. Telegram 交互壳
2. 海报 + 标准信息字段
3. metadata 主辅源重排

## 风险

- metadata 源接入太多会快速放大范围，所以应优先锁主/辅源策略，再做最小首批实现。
- Telegram 链接点击/复制能力可能涉及 formatter / markup 选择，必须先确认平台能力边界。
