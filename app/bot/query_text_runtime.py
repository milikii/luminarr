from __future__ import annotations

import re

from app.services.pure_bt import (
    BTBatchConfirmRequest,
    BTBatchPreviewRequest,
    extract_bt_search_query,
)
from app.services.pure_bt import (
    extract_bt_batch_confirm_request as extract_pure_bt_batch_confirm_request,
)
from app.services.pure_bt import (
    extract_bt_batch_preview_request as extract_pure_bt_batch_preview_request,
)

FRUSTRATION_TEXTS = frozenset({"不对", "停", "重来", "换一个", "算了", "取消"})
BT_READ_ONLY_PREFIXES = ("bt搜 ", "bt search ", "成人搜 ")
BT_PROCESSING_PATH_ALIASES = {
    "观影pt链": "media_import",
    "观影pt": "media_import",
    "pt观影链": "media_import",
    "pt观影": "media_import",
    "影视入库链": "media_import",
    "影视入库": "media_import",
    "入库链": "media_import",
    "影视": "media_import",
    "mediaimport": "media_import",
    "media-import": "media_import",
    "media_import": "media_import",
    "bt成人链": "adult_bt",
    "成人bt链": "adult_bt",
    "成人链": "adult_bt",
    "adultbt": "adult_bt",
    "adult-bt": "adult_bt",
    "adult_bt": "adult_bt",
    "纯bt下载链": "pure_bt",
    "纯bt下载": "pure_bt",
    "纯bt": "pure_bt",
    "纯磁力下载链": "pure_bt",
    "purebt": "pure_bt",
    "pure-bt": "pure_bt",
    "pure_bt": "pure_bt",
}
BT_CLASSIFICATION_ALIASES = {
    "movie": "movie",
    "film": "movie",
    "电影": "movie",
    "series": "series",
    "tv": "series",
    "show": "series",
    "电视剧": "series",
    "剧集": "series",
    "anime": "anime",
    "动漫": "anime",
    "动画": "anime",
}
RAW_BT_LEGACY_SHORTCUTS = frozenset({"raw_bt", "rawbt", "raw", "其他bt资源", "其他bt"})
_DUPLICATE_OVERRIDE_PATTERN = re.compile(r"^\s*继续下载(?:\s+.+)?\s*$", re.IGNORECASE)


def _normalize_compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text.strip()).lower()


def is_frustration_text(text: str) -> bool:
    normalized_text = _normalize_compact_text(text)
    if not normalized_text:
        return False
    return normalized_text in FRUSTRATION_TEXTS


def is_bt_direct_intent(text: str) -> bool:
    stripped_text = text.strip()
    if not stripped_text:
        return False
    lowered_text = stripped_text.lower()
    if lowered_text.startswith("magnet:?"):
        return True
    normalized_text = _normalize_compact_text(stripped_text)
    return normalized_text in {
        "下载这个bt",
        "下载这个bt种子",
        "下载这个磁力",
        "下载此bt",
        "下载此bt种子",
        "下载此磁力",
    } or bool(extract_bt_search_query(stripped_text))


def extract_bt_read_only_query(text: str) -> str:
    cleaned_text = re.sub(r"\s+", " ", text.strip())
    if not cleaned_text:
        return ""
    lowered_text = cleaned_text.lower()
    for prefix in BT_READ_ONLY_PREFIXES:
        if lowered_text.startswith(prefix):
            return cleaned_text[len(prefix) :].strip()
    return ""


def extract_bt_batch_preview_request(text: str) -> BTBatchPreviewRequest | None:
    return extract_pure_bt_batch_preview_request(text)


def extract_bt_batch_confirm_request(text: str) -> BTBatchConfirmRequest | None:
    return extract_pure_bt_batch_confirm_request(text)


def parse_bt_classification_choice(text: str) -> str | None:
    normalized_text = _normalize_compact_text(text)
    if not normalized_text:
        return None
    return BT_CLASSIFICATION_ALIASES.get(normalized_text)


def parse_bt_processing_path_choice(text: str) -> str | None:
    normalized_text = _normalize_compact_text(text)
    if not normalized_text:
        return None
    return BT_PROCESSING_PATH_ALIASES.get(normalized_text)


def parse_bt_processing_path_legacy_shortcut(text: str) -> tuple[str, str | None] | None:
    normalized_text = _normalize_compact_text(text)
    if not normalized_text:
        return None
    media_kind = BT_CLASSIFICATION_ALIASES.get(normalized_text)
    if media_kind is not None:
        return ("media_import", media_kind)
    if normalized_text in RAW_BT_LEGACY_SHORTCUTS:
        return ("pure_bt", None)
    return None


def is_duplicate_override_text(text: str) -> bool:
    return _DUPLICATE_OVERRIDE_PATTERN.match(text) is not None
