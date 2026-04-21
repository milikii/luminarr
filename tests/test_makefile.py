from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess


def _extract_makefile_target_commands(text: str, target: str) -> list[str]:
    target_match = re.search(
        rf"^{re.escape(target)}:\n((?:\t[^\n]+\n)+)",
        text,
        re.MULTILINE,
    )
    assert target_match is not None
    return [line.strip().lstrip("@") for line in target_match.group(1).splitlines() if line.strip()]


def _build_run_recipe(*, python_command: str) -> str:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    commands = _extract_makefile_target_commands(makefile_text, "run")
    recipe = " && ".join(commands)
    recipe = recipe.replace("$(ENV_FILE)", "${ENV_FILE}")
    recipe = recipe.replace("$(PYTHON) -m app.main", python_command)
    return recipe


def test_makefile_run_reports_missing_env_file_with_fix_hint(tmp_path: Path) -> None:
    recipe = _build_run_recipe(python_command='python3 -c "print(\'should-not-run\')"')
    missing_env = tmp_path / "missing.env"
    env = os.environ | {"ENV_FILE": str(missing_env)}

    result = subprocess.run(
        ["bash", "-lc", recipe],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        env=env,
        check=False,
    )

    assert result.returncode == 1
    assert "[环境文件缺失]" in result.stdout
    assert str(missing_env) in result.stdout
    assert "[处理建议]" in result.stdout
    assert "cp .env.example .env" in result.stdout
    assert "ENV_FILE=/绝对路径 make run" in result.stdout
    assert "should-not-run" not in result.stdout


def test_makefile_run_sources_absolute_env_file_before_start(tmp_path: Path) -> None:
    recipe = _build_run_recipe(
        python_command='python3 -c "import os; print(os.environ.get(\'TEST_RUN_ENV\', \'\'))"'
    )
    env_file = tmp_path / "luminarr.env"
    env_file.write_text("TEST_RUN_ENV=absolute-path-ok\n", encoding="utf-8")
    env = os.environ | {"ENV_FILE": str(env_file.resolve())}

    result = subprocess.run(
        ["bash", "-lc", recipe],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        env=env,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "absolute-path-ok"
    assert result.stderr == ""


def test_makefile_help_lists_quality_targets() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")

    assert "quality" in makefile_text
    assert "verify-mainline" in makefile_text
    assert "targets: install test quality verify-mainline" in makefile_text


def test_makefile_quality_target_keeps_fast_repo_guards_in_one_place() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    commands = _extract_makefile_target_commands(makefile_text, "quality")

    assert commands[0] == "$(MAKE) compile"
    assert commands[1] == "$(PYTHON) -m pytest -q tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py"


def test_makefile_verify_mainline_target_points_to_current_focused_regressions() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    commands = _extract_makefile_target_commands(makefile_text, "verify-mainline")

    assert commands[0] == "$(PYTHON) -m pytest -q tests/test_get_download_status.py -k \"parse_status_query or get_status_text_success or personal_wechat_channel or render_status_reply or download_monitor or completion_event or auto_import_terminal or skip_event\""
    assert commands[1] == "$(PYTHON) -m pytest -q tests/test_download_follow_up_runtime.py tests/test_telegram_bot.py -k \"download_completion or post_download_auto_import_scheduler or bt_subscription_scheduler or build_application_applies_outbound_proxy\""
    assert commands[2] == "$(PYTHON) -m pytest -q tests/test_private_chat_trace_runtime.py tests/test_private_chat_runtime.py -k trace"
    assert commands[3] == "$(PYTHON) -m pytest -q tests/test_private_chat_login_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k personal_wechat_login"
    assert commands[4] == "$(PYTHON) -m pytest -q tests/test_private_chat_bt_direct_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_bt_direct_intent_query or magnet_routes_to_bt_direct_split or bt_processing_path_persist_fails\""
    assert commands[5] == "$(PYTHON) -m pytest -q tests/test_private_chat_frustration_runtime.py tests/test_private_chat_runtime.py -k \"handle_frustration_query or cancel or pending_job_lookup_failure\""
    assert commands[6] == "$(PYTHON) -m pytest -q tests/test_private_chat_bt_batch_confirm_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_bt_batch_confirm_query or bt_batch_confirm\""
    assert commands[7] == "$(PYTHON) -m pytest -q tests/test_private_chat_bt_read_only_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_bt_read_only_query or bt_read_only_helper or bt_batch_preview\""
    assert commands[8] == "$(PYTHON) -m pytest -q tests/test_private_chat_search_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_search_query_fallback or routes_search\""
    assert commands[9] == "$(PYTHON) -m pytest -q tests/test_private_chat_status_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k status"
    assert commands[10] == "$(PYTHON) -m pytest -q tests/test_private_chat_import_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_import_query or import_routes_to_import_service or import_formats_import_approval_for_telegram or import_replies_service_not_ready\""
    assert commands[11] == "$(PYTHON) -m pytest -q tests/test_private_chat_watchlist_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_watchlist_query or watchlist_routes_to_watchlist_service or watchlist_series_routes_to_watchlist_service or watchlist_replies_service_not_ready\""
    assert commands[12] == "$(PYTHON) -m pytest -q tests/test_private_chat_bt_subscription_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_bt_subscription_query or bt_subscription_routes_to_service or bt_subscription_run_uses_bound_downloader_context or bt_subscription_replies_service_not_ready or bt_subscription_run_replies_config_missing\""
    assert commands[13] == "$(PYTHON) -m pytest -q tests/test_private_chat_cleanup_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_cleanup_query or cleanup_routes_to_cleanup_service or cleanup_inspect_routes_to_cleanup_service or cleanup_replies_service_not_ready\""
