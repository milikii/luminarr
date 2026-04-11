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
