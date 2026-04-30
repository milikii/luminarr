from __future__ import annotations

from dataclasses import dataclass

ADULT_METADATA_ROLE_PRIMARY = "primary"
ADULT_METADATA_ROLE_SUPPORTING = "supporting"
ADULT_METADATA_ROLE_CONDITIONAL = "conditional"
ADULT_METADATA_ROLE_BACKUP_CROSS_CHECK = "backup_cross_check"


@dataclass(frozen=True, slots=True)
class AdultMetadataSourceProfile:
    name: str
    role: str
    priority: float
    default_main: bool
    aliases: tuple[str, ...] = ()


_ADULT_METADATA_SOURCE_PROFILES: dict[str, AdultMetadataSourceProfile] = {
    "avmoo": AdultMetadataSourceProfile(
        name="avmoo",
        role=ADULT_METADATA_ROLE_PRIMARY,
        priority=100.0,
        default_main=True,
        aliases=("avmoo.shop", "www.avmoo.shop"),
    ),
    "avbase": AdultMetadataSourceProfile(
        name="avbase",
        role=ADULT_METADATA_ROLE_PRIMARY,
        priority=90.0,
        default_main=True,
        aliases=("avbase.net", "www.avbase.net"),
    ),
    "jav321": AdultMetadataSourceProfile(
        name="jav321",
        role=ADULT_METADATA_ROLE_PRIMARY,
        priority=80.0,
        default_main=True,
        aliases=("jav321.com", "www.jav321.com"),
    ),
    "avsox": AdultMetadataSourceProfile(
        name="avsox",
        role=ADULT_METADATA_ROLE_PRIMARY,
        priority=70.0,
        default_main=True,
        aliases=("avsox.click", "www.avsox.click"),
    ),
    "caribbeancom": AdultMetadataSourceProfile(
        name="caribbeancom",
        role=ADULT_METADATA_ROLE_PRIMARY,
        priority=60.0,
        default_main=True,
        aliases=("caribbeancom.com", "www.caribbeancom.com"),
    ),
    "missav": AdultMetadataSourceProfile(
        name="missav",
        role=ADULT_METADATA_ROLE_PRIMARY,
        priority=50.0,
        default_main=True,
        aliases=("missav123.com", "www.missav123.com"),
    ),
    "javlibrary": AdultMetadataSourceProfile(
        name="javlibrary",
        role=ADULT_METADATA_ROLE_BACKUP_CROSS_CHECK,
        priority=40.0,
        default_main=False,
        aliases=("javlibrary.com", "www.javlibrary.com"),
    ),
    "javbus": AdultMetadataSourceProfile(
        name="javbus",
        role=ADULT_METADATA_ROLE_SUPPORTING,
        priority=20.0,
        default_main=False,
        aliases=("javbus.com", "www.javbus.com"),
    ),
    "fanza": AdultMetadataSourceProfile(
        name="fanza",
        role=ADULT_METADATA_ROLE_CONDITIONAL,
        priority=10.0,
        default_main=False,
        aliases=("dmm", "dmm.co.jp", "www.dmm.co.jp", "fanza.jp", "www.dmm.com"),
    ),
}
_ADULT_METADATA_SOURCE_ALIASES: dict[str, str] = {
    alias: profile.name
    for profile in _ADULT_METADATA_SOURCE_PROFILES.values()
    for alias in (profile.name, *profile.aliases)
}
_ROLE_SORT_WEIGHT = {
    ADULT_METADATA_ROLE_PRIMARY: 3,
    ADULT_METADATA_ROLE_BACKUP_CROSS_CHECK: 2,
    ADULT_METADATA_ROLE_SUPPORTING: 1,
    ADULT_METADATA_ROLE_CONDITIONAL: 0,
}


def canonicalize_adult_metadata_source_name(value: str) -> str:
    cleaned = value.strip().lower()
    if not cleaned:
        return ""
    return _ADULT_METADATA_SOURCE_ALIASES.get(cleaned, cleaned)


def get_adult_metadata_source_profile(name: str) -> AdultMetadataSourceProfile | None:
    return _ADULT_METADATA_SOURCE_PROFILES.get(canonicalize_adult_metadata_source_name(name))


def rank_adult_metadata_sources(source_names: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    canonical_names = tuple(dict.fromkeys(canonicalize_adult_metadata_source_name(name) for name in source_names if name.strip()))
    return tuple(sorted(canonical_names, key=_adult_metadata_source_sort_key, reverse=True))


def get_default_adult_metadata_source_names() -> tuple[str, ...]:
    default_sources = [profile.name for profile in _ADULT_METADATA_SOURCE_PROFILES.values() if profile.default_main]
    return rank_adult_metadata_sources(default_sources)


def get_adult_metadata_source_rank() -> tuple[AdultMetadataSourceProfile, ...]:
    return tuple(
        sorted(
            _ADULT_METADATA_SOURCE_PROFILES.values(),
            key=lambda profile: _adult_metadata_source_sort_key(profile.name),
            reverse=True,
        )
    )


def _adult_metadata_source_sort_key(name: str) -> tuple[int, int, float, str]:
    profile = get_adult_metadata_source_profile(name)
    if profile is None:
        return (0, 0, 0.0, name)
    return (
        1 if profile.default_main else 0,
        _ROLE_SORT_WEIGHT.get(profile.role, 0),
        profile.priority,
        profile.name,
    )
