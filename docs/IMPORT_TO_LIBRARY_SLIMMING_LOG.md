# Import to library slimming log (v1)

> 目的：承接当前“`import_to_library.py` 导入编排层瘦身 / 模块化”主线的详细台账。
> 约束：`docs/STATUS.md` 只保留当前快照；新的闭环优先合并进下面分组，不逐天追加 dated 小节。

## 1. Current line

- 当前唯一主线：`import_to_library.py` 导入编排层瘦身 / 模块化
- 上一条已完成主线“`telegram_bot.py` 渠道层瘦身 / 模块化”已在 2026-04-19 满足退出条件 1；详细台账继续只看 `docs/TELEGRAM_BOT_SLIMMING_LOG.md`
- 更早主线“独立后台下载完成轮询剩余少量回归与验证收口”已完成；详细台账继续只看 `docs/DOWNLOAD_COMPLETION_POLLING_LOG.md`
- 更早主线“Feishu 私聊事件解析器去重”已完成；详细台账继续只看 `docs/FEISHU_EVENT_PARSER_DEDUPE_LOG.md`
- 更早主线“Feishu 长连接私有 API 风险收口”已完成；详细台账继续只看 `docs/FEISHU_LONG_CONNECTION_RISK_LOG.md`
- 更早主线“持久化吞错收口”已完成；详细台账继续只看 `docs/PERSISTENCE_CLOSURE_LOG.md`
- cleanup 四渠道验证窗口已完成；详细证据继续只看 `docs/CLEANUP_VERIFICATION_WINDOW.md`

## 2. Risk groups

### 2.1 导入前上下文重建 / raw_bt 判定

当前风险：
- `import_to_library.py` 仍把 confirm 上下文重建、approval 读取和 raw_bt 判定揉在同一文件；这一步只允许把这组“导入前真相重建 + fail-closed 停路”的壳继续收成更小的仓库自管 helper，不改 approval、`jobs`、`job_event` 和导入成功真相。
- 这一组只允许动导入前上下文重建和 raw_bt 判定；不顺手改 confirm 协议、pending / expired / stale 边界和现有中文日志。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "context_lookup or context_row_corruption or raw_bt"`

### 2.2 执行模式 / copy-fallback / 文件系统导入执行 / metadata / subtitle / refresh 收尾

当前风险：
- `import_to_library.py` 还把硬链接 / copy-fallback、文件系统导入执行，以及 metadata / subtitle / refresh 收尾混在同一文件；这一步只允许按一组连贯 helper 拆开，不能顺手改 approval、`jobs`、`job_event`、导入成功真相或后置动作协议。
- 这一组继续守住“导入成功是真相，metadata / subtitle / refresh 失败不回滚导入成功”的边界，并保持显式中文日志 + `[处理建议]`。

focused tests 入口：
- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "copy_fallback or cross_filesystem or hardlink_failure or metadata_scrape or subtitle_translate or refresh"`

## 3. Focused verification

- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "context_lookup or context_row_corruption or raw_bt"`
- `.venv/bin/python -m pytest -q tests/test_import_to_library.py -k "copy_fallback or cross_filesystem or hardlink_failure or metadata_scrape or subtitle_translate or refresh"`
- `.venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py`

## 4. Maintenance rule

- 补完一个最小闭环后，先判断它属于 2.1~2.2 哪个风险分组，把路径或行为差异合并进去；不要新增 dated 小节。
- `docs/STATUS.md` 最多补一句当前结论或一条最新风险；不回灌长台账。
- 只有当当前主线完成并切到下一项时，才在 `docs/NEXT_STEP.md` 和 `README.md` 切换“当前唯一主线”。
