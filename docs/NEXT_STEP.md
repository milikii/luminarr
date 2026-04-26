# Next step (v375)

## Current goal

- 当前唯一主线切到 **`downloader_route_lookup.py` 重复日志/路由壳收口 / 质量硬化**。
- 当前这一轮只服务两件事：
  - 收掉 `downloader_route_lookup.py` 里重复的日志函数和同构的路由序幕
  - 保持刚完成的 cleanup 支持文件收口、重复 trace logger 收口、`_COMPAT_REEXPORTS` 清理、`config.py` 重复解析逻辑收口、docs 归档减法、`search_media.py` / `import_to_library.py` 冻结态和 downloader adult registry 收口完成态，不回退
- 已完成态保持，不回退：
  - `Makefile` 公开验证入口已收口：`verify-mainline` 当前改成 4 个分组 target 汇总入口，cleanup 公开入口收敛到 `test-cleanup-smoke` / `test-cleanup` / `test-cleanup-docs-gate` / `test-cleanup-window`
  - `docs/OPERATOR_RUNBOOK.md` / `docs/GETTING_STARTED.md` 当前已去掉过时主线残留和重复入口
  - `docs/` 主目录历史施工文档已归档到 `archive/docs/`
  - 成人 BT 站点优先、历史账本、只读补全、归档与保留期清理
  - 更早完成的 **shared runtime 对 `telegram_bot.py` 内部 helper 的直接依赖收口** 继续保持完成态
  - `app/services/add_adult_registry_state.py` 已承接 adult pending / downloading 状态写入；`add_to_downloader.py` 当前 `582` 行，只剩 proof-like wrapper
  - `search_media.py` 当前 `288` 行，歧义澄清 / media-BT 排序 / batch preview 页面支持 helper 已抽到独立模块
  - `import_to_library.py` 当前 `590` 行，confirmed media identity 回查已抽到 `app/services/import_confirmed_media_identity.py`，focused gate + pyflakes 复评估已确认当前没有 worth-it 闭环
  - `app/bot/private_chat_runtime.py` 当前 `476` 行，`app/bot/telegram_bot.py` 当前 `276` 行，不回退
  - cleanup 链当前已不再保留 `cleanup_*_support.py` 文件；相关逻辑已经收回 `cleanup_downloaded_source.py`、`cleanup_correlation_lookup.py` 和 `adult_archive_service.py`
  - `app/services/workflow_trace_logger.py` 已落地；`AddToDownloaderService` 与 `ImportToLibraryService` 都已直接改用共享实现，不再保留 workflow 专属 trace logger 文件
  - `app/config.py` 当前 `454` 行，`RAW_BT_DESTINATIONS`、`ADULT_ARCHIVE_DESTINATIONS`、`DOWNLOADER_INSTANCES` 已共用分条/分段解析 helper
- `app/downloader_route_lookup.py` 当前 `492` 行；共享 route lookup / dispatch 日志打印器、client candidate 纯解析 helper、payload key 读取壳与 import/status/remove 路由的共享前半段 helper 已落地

## User value

- 当前默认分支已经把 docs 归档、cleanup 支持文件、重复 trace logger、`_COMPAT_REEXPORTS` 和 `config.py` 重复解析都收口完成；接下来最有价值的是先收 `downloader_route_lookup.py` 里重复的日志/路由壳。
- 这一步只允许对下载器路由的重复日志/路由边界做最小闭环，不碰搜索真相、下载确认协议、shared runtime 或新的展示层扩展。
- 先把路由重复壳压薄，后续才有资格再评估更大的下载器路由结构债。

## Only do

- 只在 `downloader_route_lookup.py` 这条线里动下面这些稳定边界：
  - `_log_*` 函数继续优先复用共享打印器
  - 实例查找 + client 选择继续优先复用纯解析 helper
  - 3 个路由函数里可提取的公共序幕
  - 不改变现有错误文本、路由语义或导入/状态协议
- 每轮仍只做一个最小闭环；同步补对应 focused tests、`docs/STATUS.md`、`docs/NEXT_STEP.md` 和相关主线文档。
- 继续保持当前 downloader / 搜索 / 导入 / 成人 BT / 验证入口已收口真相与文档一致。

## Do not do

- 不回头重建任何 `cleanup_*_support.py`、workflow trace 壳、`_COMPAT_REEXPORTS` 兼容 tuple 或 `config.py` 的重复解析壳。
- 不在这一步顺手改路由协议、下游服务真相、环境变量名、默认值或报错文本。
- 不把路由收口又扩成新的大扫除；没有显式主线时，不顺手碰消息展示层、`.env.example` 或 `AGENTS.md`。

## Done when

当前这条 **`downloader_route_lookup.py` 重复日志/路由壳收口 / 质量硬化** 主线满足：

1. `_log_*` 函数数量下降，且优先通过共享实现而不是复制新日志壳来收口。
2. `tests/test_downloader_route_lookup.py`、`tests/test_main.py` 与相关 focused gate 仍通过。
3. `docs/STATUS.md`、`docs/NEXT_STEP.md` 对当前路由收口方向和下一候选结构债表述一致。

## After this step

1. 如果路由线也收得差不多了，再评估 `_COMPAT_REEXPORTS` 的残余依赖或更大的配置层结构债。
2. 如果后续想切去用户可感知改进，再看 `docs/SEARCH_REPLY_PRESENTATION_PLAN.md`。
