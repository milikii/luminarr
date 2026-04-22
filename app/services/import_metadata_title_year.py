from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.services.import_prepare_state import extract_title_year_for_scrape, extract_title_year_from_text

ResolveNormalizedNamingTruthFunc = Callable[..., str]


class ImportMetadataTitleYearResolver:
    def __init__(
        self,
        *,
        resolve_normalized_naming_truth_func: ResolveNormalizedNamingTruthFunc,
    ) -> None:
        self._resolve_normalized_naming_truth = resolve_normalized_naming_truth_func

    def resolve(self, *, task_id: str, task_hash: str, target_path: Path) -> tuple[str, str]:
        fallback_title, fallback_year = extract_title_year_for_scrape(target_path)
        naming_truth = self._resolve_normalized_naming_truth(
            task_id=task_id,
            task_hash=task_hash,
            fallback_name="",
        )
        if not naming_truth:
            return fallback_title, fallback_year

        title_from_truth, year_from_truth = extract_title_year_from_text(naming_truth)
        title = title_from_truth or fallback_title
        year = year_from_truth or fallback_year
        return title, year
