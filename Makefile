SHELL := /bin/bash
PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
ENV_FILE ?= .env

.PHONY: help install test test-cleanup-smoke test-cleanup-service-not-ready test-cleanup-telegram test-cleanup-personal-wechat test-cleanup-feishu test-cleanup-wecom test-cleanup-feishu-webhook test-cleanup test-docs test-cleanup-docs-gate test-cleanup-window sync-cleanup-doc-snapshots compile run docker-build docker-up docker-logs

help:
	@printf '%s\n' 'targets: install test test-cleanup-smoke test-cleanup-service-not-ready test-cleanup-telegram test-cleanup-personal-wechat test-cleanup-feishu test-cleanup-wecom test-cleanup-feishu-webhook test-cleanup test-docs test-cleanup-docs-gate test-cleanup-window sync-cleanup-doc-snapshots compile run docker-build docker-up docker-logs'

install:
	$(PIP) install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

test-cleanup-smoke:
	$(PYTHON) -m pytest -q tests/test_cleanup_cross_channel_smoke.py

test-cleanup-service-not-ready:
	$(PYTHON) -m pytest -q tests/test_cleanup_cross_channel_smoke.py -k service_not_ready

test-cleanup-telegram:
	$(PYTHON) -m pytest -q tests/test_telegram_bot.py -k cleanup

test-cleanup-personal-wechat:
	$(PYTHON) -m pytest -q tests/test_personal_wechat_text.py -k cleanup

test-cleanup-feishu:
	$(PYTHON) -m pytest -q tests/test_feishu_adapter.py -k cleanup

test-cleanup-wecom:
	$(PYTHON) -m pytest -q tests/test_wecom_adapter.py -k cleanup

test-cleanup-feishu-webhook:
	$(PYTHON) -m pytest -q tests/test_feishu_adapter.py -k "webhook_http_request and cleanup"

test-cleanup:
	$(PYTHON) -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup

test-docs:
	$(PYTHON) -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py

test-cleanup-docs-gate:
	$(PYTHON) -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py

test-cleanup-window:
	$(MAKE) test-cleanup-smoke
	$(MAKE) test-cleanup
	$(MAKE) test-cleanup-docs-gate

sync-cleanup-doc-snapshots:
	$(PYTHON) -m app.maintenance.cleanup_verification_docs full_suite cleanup_service smoke_gate focused_cleanup docs_gate focused_config makefile_env_guard compile_check docs_consistency env_readiness local_smoke_evidence

compile:
	python3 -m compileall app tests

run:
	@if [ ! -f "$(ENV_FILE)" ]; then printf '\033[31m[环境文件缺失]\033[0m 未找到启动所需环境文件：%s\n\033[33m[处理建议]\033[0m 先执行 cp .env.example .env，再补齐最小必填项；如果环境文件不在仓库根目录，请使用 ENV_FILE=/绝对路径 make run。\n' "$(ENV_FILE)"; exit 1; fi
	@set -a && . "$(ENV_FILE)" && set +a && $(PYTHON) -m app.main

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-logs:
	docker compose logs -f luminarr
