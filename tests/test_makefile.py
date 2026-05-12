from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


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


def test_makefile_run_accepts_shell_safe_semicolon_env_values(tmp_path: Path) -> None:
    recipe = _build_run_recipe(
        python_command='python3 -c "import os; print(os.environ.get(\'DOWNLOADER_INSTANCES\', \'\'))"'
    )
    env_file = tmp_path / "luminarr.env"
    env_file.write_text(
        'DOWNLOADER_INSTANCES="tr-pt|transmission|http://127.0.0.1:19091|/data/downloads/tr;tr-bt|transmission|http://127.0.0.1:19092|/data/downloads/tr-bt"\n',
        encoding="utf-8",
    )
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
    assert result.stdout.strip() == "tr-pt|transmission|http://127.0.0.1:19091|/data/downloads/tr;tr-bt|transmission|http://127.0.0.1:19092|/data/downloads/tr-bt"
    assert result.stderr == ""


def test_makefile_help_lists_quality_targets() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")

    assert "quality" in makefile_text
    assert "lint" in makefile_text
    assert "test-downloader-focused" in makefile_text
    assert "test-import-focused" in makefile_text
    assert "verify-quality-gates" in makefile_text
    assert "verify-mainline" in makefile_text
    assert "verify-stage1" in makefile_text
    assert "verify-subtitle-provider-smoke" in makefile_text
    assert (
        "targets: install test quality lint test-downloader-focused "
        "test-import-focused verify-quality-gates verify-mainline verify-stage1 verify-adult-bt-wedge "
        "verify-subtitle-provider-smoke "
        "test-cleanup-smoke test-cleanup test-docs test-cleanup-docs-gate "
        "test-cleanup-window sync-cleanup-doc-snapshots compile run "
        "docker-build docker-up docker-logs"
    ) in makefile_text


def test_makefile_quality_target_keeps_fast_repo_guards_in_one_place() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    commands = _extract_makefile_target_commands(makefile_text, "quality")

    assert commands[0] == "$(MAKE) compile"
    assert commands[1] == "$(MAKE) lint"
    assert commands[2] == "$(PYTHON) -m pytest -q tests/test_makefile.py tests/test_cleanup_docs_consistency.py tests/test_cleanup_verification_window_doc.py"


def test_makefile_lint_target_points_to_repo_static_guard() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    commands = _extract_makefile_target_commands(makefile_text, "lint")

    assert commands == ["$(PYTHON) -m ruff check app tests"]


def test_makefile_quality_gate_targets_point_to_current_focused_regressions() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")

    downloader_commands = _extract_makefile_target_commands(makefile_text, "test-downloader-focused")
    assert downloader_commands == [
        "$(PYTHON) -m pytest -q tests/test_add_execution_follow_up.py tests/test_add_to_downloader.py tests/test_private_chat_confirm_runtime.py"
    ]

    import_commands = _extract_makefile_target_commands(makefile_text, "test-import-focused")
    assert import_commands == [
        "$(PYTHON) -m pytest -q tests/test_import_pending_write_through_state.py tests/test_import_to_library.py -k \"import_by_task_ref or record_pending_approval or pending_state_unavailable or copy_fallback_pending\""
    ]

    verify_commands = _extract_makefile_target_commands(makefile_text, "verify-quality-gates")
    assert verify_commands == [
        "$(MAKE) test",
        "$(MAKE) test-downloader-focused",
        "$(MAKE) test-import-focused",
    ]


def test_makefile_verify_adult_bt_wedge_target_points_to_current_focused_regressions() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")

    assert "verify-adult-bt-wedge" in makefile_text
    assert (
        "targets: install test quality lint test-downloader-focused "
        "test-import-focused verify-quality-gates verify-mainline verify-stage1 verify-adult-bt-wedge "
        "verify-subtitle-provider-smoke "
        "test-cleanup-smoke test-cleanup test-docs test-cleanup-docs-gate "
        "test-cleanup-window sync-cleanup-doc-snapshots compile run "
        "docker-build docker-up docker-logs"
    ) in makefile_text

    commands = _extract_makefile_target_commands(makefile_text, "verify-adult-bt-wedge")
    assert commands == [
        "$(PYTHON) -m pytest -q tests/test_query_text_runtime.py tests/test_bt_read_only_display.py tests/test_search_media.py",
        "$(PYTHON) -m pytest -q tests/test_add_pending_context.py tests/test_add_to_downloader.py tests/test_private_chat_runtime.py",
        "$(PYTHON) -m pytest -q tests/test_adult_archive_service.py tests/test_get_download_status.py",
    ]


def test_makefile_verify_subtitle_provider_smoke_target_points_to_module_entrypoint() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")

    assert "verify-subtitle-provider-smoke" in makefile_text
    commands = _extract_makefile_target_commands(makefile_text, "verify-subtitle-provider-smoke")

    assert commands == [
        'if [ ! -f "$(ENV_FILE)" ]; then printf \'\\033[31m[环境文件缺失]\\033[0m 未找到字幕 provider 自检所需环境文件：%s\\n\\033[33m[处理建议]\\033[0m 先执行 cp .env.example .env，再补齐 SUBTITLE_TRANSLATION_*；如果环境文件不在仓库根目录，请使用 ENV_FILE=/绝对路径 make verify-subtitle-provider-smoke。\\n\' "$(ENV_FILE)"; exit 1; fi',
        'set -a && . "$(ENV_FILE)" && set +a && $(PYTHON) -m app.maintenance.verify_subtitle_provider_smoke',
    ]


def test_makefile_verify_mainline_target_points_to_current_focused_regressions() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    commands = _extract_makefile_target_commands(makefile_text, "verify-mainline")

    assert commands == [
        "$(MAKE) verify-mainline-status-and-channels",
        "$(MAKE) verify-mainline-bt-paths",
        "$(MAKE) verify-mainline-execution-paths",
        "$(MAKE) verify-mainline-user-intents",
    ]


def test_makefile_verify_stage1_target_points_to_current_focused_regressions() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    commands = _extract_makefile_target_commands(makefile_text, "verify-stage1")

    assert commands == [
        "$(MAKE) verify-stage1-duplicate-memory",
        "$(MAKE) verify-stage1-telegram-delivery",
        "$(MAKE) verify-stage1-bt-source-roles",
    ]


def test_makefile_verify_stage1_duplicate_memory_group_keeps_current_regressions() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    commands = _extract_makefile_target_commands(makefile_text, "verify-stage1-duplicate-memory")

    assert commands == [
        "$(PYTHON) -m pytest -q tests/test_persistence_sqlite.py -k adult_duplicate_memory_snapshot",
        "$(PYTHON) -m pytest -q tests/test_adult_duplicate_memory.py tests/test_adult_duplicate_memory_tools.py",
        "$(PYTHON) -m pytest -q tests/test_add_to_downloader.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k duplicate",
    ]


def test_makefile_verify_stage1_telegram_delivery_group_keeps_current_regressions() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    commands = _extract_makefile_target_commands(makefile_text, "verify-stage1-telegram-delivery")

    assert commands == [
        "$(PYTHON) -m pytest -q tests/test_delivery_renderers.py tests/test_telegram_delivery_runtime.py",
        "$(PYTHON) -m pytest -q tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"routes_search_with_channel_delivery_renderer or routes_add_pending_with_channel_delivery_renderer or routes_status_with_channel_delivery_renderer or import_formats_import_approval_for_telegram or routes_duplicate_override_follow_up\"",
        "$(PYTHON) -m pytest -q tests/test_search_media.py tests/test_telegram_reply_formatter.py -k \"prefers_media_confirmation_for_strong_cjk_title_before_resource_search or keeps_non_telegram_candidate_confirmation_layout_intact or formats_media_candidate_confirmation_with_primary_hero_block or sends_local_posters_before_candidate_confirmation_text or keeps_single_candidate_followup_minimal_after_local_poster_send or adds_html_candidate_caption_and_per_card_button or uses_placeholder_media_for_posterless_candidate_in_mixed_list or refills_failed_candidate_poster_block_into_text\"",
        "$(PYTHON) -m pytest -q tests/test_search_media.py tests/test_telegram_pt_resource_cards.py tests/test_telegram_runtime_adapter.py -k \"returns_telegram_pt_card_marker_after_media_lock or pt_resource or consumes_pt_resource_card or rejects_cancelled_pt_resource_card\"",
        "$(PYTHON) -m pytest -q tests/test_add_to_downloader.py -k pt_resource_card_task_ref",
    ]


def test_makefile_verify_stage1_bt_source_roles_group_keeps_current_regressions() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    commands = _extract_makefile_target_commands(makefile_text, "verify-stage1-bt-source-roles")

    assert commands == [
        "$(PYTHON) -m pytest -q tests/test_bt_sources.py -k \"registry_tracks_roles_and_helper_only_gate or default_adult_bt_sources_are_active_resource_providers_only or get_configured_web_source_rule_skips_helper_only_source or get_configured_web_source_rule_skips_supported_but_unmodeled_source\"",
        "$(PYTHON) -m pytest -q tests/test_bt_read_only_display.py tests/test_search_media.py -k \"javlibrary or helper_only or uncensored_helper\"",
        "$(PYTHON) -m pytest -q tests/test_adult_read_only_helper_chain.py tests/test_avmoo_helper.py tests/test_avsox_helper.py tests/test_javbus_helper.py tests/test_caribbeancom_helper.py tests/test_javlibrary_helper.py",
        "$(PYTHON) -m pytest -q tests/test_main.py -k \"build_bt_source_providers_skips_helper_only_web_sources or build_bt_source_providers_uses_curated_adult_defaults_when_config_empty or build_bt_source_providers_skips_supported_but_unmodeled_web_sources or build_adult_read_only_lookup_func_wires_avmoo_before_javlibrary\"",
    ]


def test_makefile_verify_mainline_status_and_channels_group_keeps_current_regressions() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    commands = _extract_makefile_target_commands(makefile_text, "verify-mainline-status-and-channels")

    assert commands == [
        "$(PYTHON) -m pytest -q tests/test_get_download_status.py -k \"parse_status_query or get_status_text_success or personal_wechat_channel or render_status_reply or download_monitor or completion_event or auto_import_terminal or skip_event\"",
        "$(PYTHON) -m pytest -q tests/test_download_follow_up_runtime.py tests/test_telegram_bot.py -k \"download_completion or post_download_auto_import_scheduler or bt_subscription_scheduler or build_application_applies_outbound_proxy\"",
        "$(PYTHON) -m pytest -q tests/test_telegram_runtime_adapter.py tests/test_feishu_adapter.py tests/test_personal_wechat_text.py tests/test_wecom_adapter.py -k \"routes_into_shared_runtime or routes_through_dispatch_private_chat_text or polls_single_saved_account_and_replies or callback_http_request_routes_post_into_shared_runtime_and_returns_encrypted_reply\"",
        "$(PYTHON) -m pytest -q tests/test_private_chat_trace_runtime.py tests/test_private_chat_runtime.py -k trace",
        "$(PYTHON) -m pytest -q tests/test_private_chat_login_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k personal_wechat_login",
    ]


def test_makefile_verify_mainline_bt_paths_group_keeps_current_regressions() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    commands = _extract_makefile_target_commands(makefile_text, "verify-mainline-bt-paths")

    assert commands == [
        "$(PYTHON) -m pytest -q tests/test_private_chat_bt_direct_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_bt_direct_intent_query or magnet_routes_to_bt_direct_split or bt_processing_path_persist_fails\"",
        "$(PYTHON) -m pytest -q tests/test_private_chat_bt_processing_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_bt_processing_path_follow_up or bt_processing_path_media_import_choice or bt_processing_path_pure_bt_choice or bt_processing_path_payload_corruption\"",
        "$(PYTHON) -m pytest -q tests/test_private_chat_bt_classification_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_bt_classification_follow_up or bt_classification_reply_when_pending or bt_classification_payload_corruption\"",
        "$(PYTHON) -m pytest -q tests/test_private_chat_bt_tmdb_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_bt_tmdb_follow_up or bt_tmdb_association_succeeds_for_movie or bt_tmdb_lookup_failure\"",
        "$(PYTHON) -m pytest -q tests/test_private_chat_raw_bt_destination_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_raw_bt_destination_follow_up or raw_bt_destination_selection_succeeds or raw_bt_destination_lookup_failure\"",
        "$(PYTHON) -m pytest -q tests/test_telegram_downloader_execution_runtime.py -k resolve_telegram",
        "$(PYTHON) -m pytest -q tests/test_telegram_bot.py -k \"bt_processing_path_pending or bt_classification_pending or bt_tmdb_association_pending or raw_bt_destination_pending\"",
        "$(PYTHON) -m pytest -q tests/test_telegram_bot.py -k \"enter_media_import_bt_flow or enter_pure_bt_flow\"",
    ]


def test_makefile_verify_mainline_execution_paths_group_keeps_current_regressions() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    commands = _extract_makefile_target_commands(makefile_text, "verify-mainline-execution-paths")

    assert commands == [
        "$(PYTHON) -m pytest -q tests/test_private_chat_downloader_execution_runtime.py -k resolve_private_chat_bound_downloader_execution",
        "$(PYTHON) -m pytest -q tests/test_private_chat_frustration_runtime.py tests/test_private_chat_runtime.py -k \"handle_frustration_query or cancel or pending_job_lookup_failure\"",
        "$(PYTHON) -m pytest -q tests/test_private_chat_bt_batch_confirm_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_bt_batch_confirm_query or bt_batch_confirm\"",
        "$(PYTHON) -m pytest -q tests/test_private_chat_bt_read_only_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_bt_read_only_query or bt_read_only_helper or bt_batch_preview\"",
        "$(PYTHON) -m pytest -q tests/test_private_chat_confirm_runtime.py tests/test_private_chat_selection_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_confirm_query or confirm_routes or handle_digit_selection_query or digit_routes_to_add_service or digit_uses_callback_context_when_effective_context_missing or digit_replies_service_not_ready or digit_blocked_when_clarification_pending\"",
    ]


def test_makefile_verify_mainline_user_intents_group_keeps_current_regressions() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    commands = _extract_makefile_target_commands(makefile_text, "verify-mainline-user-intents")

    assert commands == [
        "$(PYTHON) -m pytest -q tests/test_private_chat_search_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_search_query_fallback or routes_search\"",
        "$(PYTHON) -m pytest -q tests/test_private_chat_status_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k status",
        "$(PYTHON) -m pytest -q tests/test_private_chat_import_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_import_query or import_routes_to_import_service or import_formats_import_approval_for_telegram or import_replies_service_not_ready\"",
        "$(PYTHON) -m pytest -q tests/test_private_chat_watchlist_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_watchlist_query or watchlist_routes_to_watchlist_service or watchlist_series_routes_to_watchlist_service or watchlist_replies_service_not_ready\"",
        "$(PYTHON) -m pytest -q tests/test_private_chat_bt_subscription_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_bt_subscription_query or bt_subscription_routes_to_service or bt_subscription_run_uses_bound_downloader_context or bt_subscription_replies_service_not_ready or bt_subscription_run_replies_config_missing\"",
        "$(PYTHON) -m pytest -q tests/test_private_chat_cleanup_runtime.py tests/test_private_chat_runtime.py tests/test_telegram_bot.py -k \"handle_cleanup_query or cleanup_routes_to_cleanup_service or cleanup_inspect_routes_to_cleanup_service or cleanup_replies_service_not_ready\"",
    ]
