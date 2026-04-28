from __future__ import annotations

VALID_MEDIA_KINDS = frozenset({"movie", "series", "anime"})

MEDIA_KIND_ALIASES = {
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

MEDIA_KIND_LABELS = {
    "movie": "电影",
    "series": "剧集",
    "anime": "动漫",
}


def media_kind_label(media_kind: str, *, default_media_kind: str = "movie") -> str:
    cleaned_kind = media_kind.strip().lower()
    default_label = MEDIA_KIND_LABELS[default_media_kind]
    return MEDIA_KIND_LABELS.get(cleaned_kind, default_label)


def parse_media_kind_prefix(raw_text: str, *, default_media_kind: str) -> tuple[str, str]:
    cleaned_text = raw_text.strip()
    if not cleaned_text:
        return default_media_kind, ""

    head, separator, tail = cleaned_text.partition(" ")
    direct_media_kind = MEDIA_KIND_ALIASES.get(head.strip().lower())
    if not separator:
        if direct_media_kind is not None:
            return direct_media_kind, ""
        return default_media_kind, cleaned_text

    if direct_media_kind is None:
        return default_media_kind, cleaned_text
    return direct_media_kind, tail.strip()
