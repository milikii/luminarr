# reimport akron to formal library

## Goal

把正式库中的 `Akron` 样本按当前已完成的新导入链路重新导入为成品结构，并实际刷新 `Emby`，验证新刮削链路在正式库可用。

## What I already know

* 旧正式库条目仍是 `/data/library/movies/Akron DDP2 H NZMA E264.mkv`
* 新链路已经在临时库真实回归通过，能生成：
  * `爱的进行时 (2015).mkv`
  * `metadata.json`
  * `nfo`
  * `poster`
  * `backdrop`
* 下载源文件仍在：`/data/downloads/tr/Akron.2015.1080p.AMZN.WEB-DL.DDP2.0.H.264-NZMA.mkv`
* 数据库中已存在该任务：
  * `task_ref=20`
  * `task_id=20`
  * `task_hash=b49089c888d789d96a989acd709e7437a234c102`
* `.env` 中正式运行所需配置已存在：
  * SQLite
  * TMDB
  * 字幕翻译
  * Emby

## Requirements

* 使用项目现有 `ImportToLibraryService` 正式重导入 `task_ref=20`
* 导入目标应落到正式库并采用当前成品命名
* 导入后应实际触发一次媒体库刷新
* 本轮不删除旧的 `Akron DDP2 H NZMA E264.*` 历史文件

## Acceptance Criteria

* [ ] 正式库出现 `爱的进行时 (2015)/...` 成品结构
* [ ] 目录内存在视频、metadata、nfo、poster、backdrop
* [ ] job_event 中出现新的 metadata / subtitle / refresh 事件
* [ ] 刷新结果不是推测，而是有实际执行证据

## Out of Scope

* 清理旧 `Akron DDP2 H NZMA E264.*` 文件
* 处理 Emby 内可能出现的重复条目
* 继续修改刮削实现代码

## Technical Notes

* 本任务优先走现有导入服务，不手工搬运文件
* 若出现目标已存在，先记录现状，再决定是否需要人工清理或单独迁移旧条目
