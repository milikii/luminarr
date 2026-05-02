# brainstorm: docker runtime deps

## Goal

补齐 Docker 部署路径所需的运行时依赖，确保容器启动后不会因为缺少 `ffmpeg` / `ffprobe` 这类字幕翻译依赖而在真实导入链里掉功能，同时把 operator-facing 文档更新成与镜像真相一致。

## What I already know

* 当前字幕翻译主线已经接好，外挂字幕可直接翻译；内嵌字幕探测 / 提取依赖 `ffmpeg` / `ffprobe`。
* 当前 [Dockerfile](/home/alex/projects/luminarr/Dockerfile) 只基于 `python:3.12-slim` 安装 Python 依赖，没有安装 `ffmpeg`。
* 当前 [docker-compose.yml](/home/alex/projects/luminarr/docker-compose.yml) 直接使用这个 Dockerfile 构建镜像，没有额外挂载宿主机二进制。
* 当前 [docs/GETTING_STARTED.md](/home/alex/projects/luminarr/docs/GETTING_STARTED.md)、[README.md](/home/alex/projects/luminarr/README.md)、[.env.example](/home/alex/projects/luminarr/.env.example) 都仍把 `ffmpeg` / `ffprobe` 描述成统一的运行时外部依赖。

## Assumptions (temporary)

* Docker 路径应该内置 `ffmpeg`，而不是要求 operator 额外在宿主机或容器外补装。
* `ffmpeg` Debian 包会一并提供 `ffprobe`，足以满足当前字幕翻译路径。
* 本轮不改字幕翻译逻辑本身，只改镜像依赖和文档真相。

## Open Questions

* 是否还存在除 `ffmpeg` / `ffprobe` 之外、当前 Docker 路径缺失但字幕翻译或相关导入链隐式依赖的系统包？

## Requirements (evolving)

* Docker 镜像必须内置 `ffmpeg`，以支持英文内嵌字幕探测 / 提取。
* 容器路径文档必须明确：Docker 镜像内已自带 `ffmpeg` / `ffprobe`；本地 Python 运行时仍需宿主机自备。
* 不引入与本任务无关的新系统依赖。

## Acceptance Criteria (evolving)

* [ ] `Dockerfile` 安装了字幕翻译所需的系统依赖。
* [ ] operator-facing 文档与 `.env.example` 已同步说明 Docker 路径与本地 Python 路径的差异。
* [ ] 至少一轮 Docker 相关静态验证通过（如 `docker compose config` / `docker build` 级别验证，视环境可用性而定）。

## Definition of Done (team quality bar)

* Tests added/updated when behavior or contract needs regression coverage
* Lint / relevant verification green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* 不改字幕翻译业务逻辑。
* 不扩容器到 personal WeChat 登录态、Feishu、WeCom 之外的新系统集成。
* 不把所有宿主运行依赖都搬进镜像；只补当前字幕翻译硬依赖和必要文档真相。

## Technical Notes

* Files inspected:
  - `Dockerfile`
  - `docker-compose.yml`
  - `docs/GETTING_STARTED.md`
  - `.env.example`
  - `README.md`
