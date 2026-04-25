from __future__ import annotations

import shutil
from pathlib import Path


def delete_cleanup_source_asset(*, source_path: Path, source_type_unsupported_text: str) -> None:
    if source_path.is_dir():
        shutil.rmtree(source_path)
        return
    if source_path.is_file():
        source_path.unlink()
        return
    raise OSError(source_type_unsupported_text)
