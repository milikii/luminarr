SHELL := /bin/bash
PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
ENV_FILE ?= .env

.PHONY: help install test test-cleanup test-docs compile run

help:
	@printf '%s\n' 'targets: install test test-cleanup test-docs compile run'

install:
	$(PIP) install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

test-cleanup:
	$(PYTHON) -m pytest -q tests/test_cleanup_cross_channel_smoke.py tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py tests/test_personal_wechat_text.py tests/test_feishu_adapter.py tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup

test-docs:
	$(PYTHON) -m pytest -q tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py

compile:
	python3 -m compileall app tests

run:
	set -a && . ./$(ENV_FILE) && set +a && $(PYTHON) -m app.main
