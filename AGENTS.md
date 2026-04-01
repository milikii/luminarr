# Luminarr AGENTS.md

## Project goal
Luminarr is a narrow vertical media automation agent.

Core responsibilities:
- search media
- add to downloader
- check task status
- import to library using hardlinks when possible
- refresh media server
- manage watchlist

## Product constraints
- Telegram is the primary channel.
- WeChat is later-phase only.
- Keep the runtime minimal and explicit.
- Do not introduce heavy agent frameworks unless explicitly asked.
- Keep Docker Compose as the deployment target.
- Assume a shared `/data` root inside containers.
- Never assume hardlinks work across filesystems.
- Keep natural language UX, but execute actions via structured tools and workflows.

## Scope discipline
Do not expand into:
- general office automation
- generic knowledge assistant behavior
- multi-purpose agent platform features
- broad plugin marketplace design in v1

## Engineering conventions
- Use Python 3.12 style.
- Prefer small files and explicit functions.
- Keep functions focused and readable.
- Prefer minimal dependencies.
- Add tests for every non-trivial change.
- Keep changes scoped to the requested task.
- Update README or docs when behavior changes.

## Architecture assumptions
- app/bot: channel entry and routing
- app/agent: planner, schemas, tool registry, workflow orchestration
- app/clients: external API clients
- app/services: business logic
- app/db: persistence
- app/jobs: scheduler jobs
- tests: automated tests

## Primary workflow priority
Always prioritize the main chain:
1. search
2. select
3. add to downloader
4. monitor status
5. import to library
6. refresh media server

## Definition of done
A task is done only when:
1. code is complete
2. tests pass
3. manual acceptance steps are provided
4. relevant docs are updated
5. no obvious regression remains

## Useful commands
- run app: `python -m app.main`
- run tests: `pytest -q`
- format: `python -m black .`
- lint: `python -m ruff check .`

## Codex operating rules
- Always start with a plan for non-trivial tasks.
- Prefer minimal diffs.
- Do not refactor unrelated modules.
- If repeating the same mistake, perform a short retrospective and update this file.
- Before finishing, run tests and review the diff.
