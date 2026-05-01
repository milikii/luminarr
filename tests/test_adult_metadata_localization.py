from __future__ import annotations

from app.services.search_reply_formatter import format_adult_metadata_lines


def test_format_adult_metadata_lines_prefers_multi_source_localized_consensus() -> None:
    lines = format_adult_metadata_lines(
        {
            "read_only_adult_display_id": "SSIS-555",
            "read_only_adult_title": "SSIS-555 サンプル作品",
            "read_only_adult_series": "サンプルシリーズ",
            "read_only_adult_actors": ("サンプルりり",),
            "adult_metadata_candidates": (
                {
                    "source_site": "avmoo",
                    "adult_title_zh": "SSIS-555 中文样片",
                    "adult_series_zh": "中文样片系列",
                    "adult_actors_zh": ("样片莉莉",),
                },
                {
                    "source_site": "javbus",
                    "adult_title_zh": "SSIS-555 中文样片",
                    "adult_series_zh": "中文样片系列",
                    "adult_actors_zh": ("样片莉莉",),
                },
            ),
        }
    )

    assert "标准信息: 标题: SSIS-555 中文样片 | 原名: SSIS-555 サンプル作品" in lines
    assert (
        "制作信息: 系列: 中文样片系列 | 原系列: サンプルシリーズ | "
        "演员: 样片莉莉 | 原演员: サンプルりり"
    ) in lines


def test_format_adult_metadata_lines_uses_trusted_chinese_aliases() -> None:
    lines = format_adult_metadata_lines(
        {
            "read_only_adult_display_id": "SSIS-483",
            "read_only_adult_source_site": "avmoo.shop",
            "read_only_adult_title": "シン・交わる体液、濃密セックス 完全ノーカット5本番",
            "read_only_adult_series": "交わる体液、濃密セックス",
            "read_only_adult_actors": ("七ツ森りり",),
        }
    )

    assert (
        "标准信息: 标题: 新·交融的体液、浓密性爱 完全未删减 5本番 | "
        "原名: シン・交わる体液、濃密セックス 完全ノーカット5本番"
    ) in lines
    assert (
        "制作信息: 系列: 交融的体液、浓密性爱 | 原系列: 交わる体液、濃密セックス | "
        "演员: 七森莉莉 | 原演员: 七ツ森りり"
    ) in lines


def test_format_adult_metadata_lines_uses_translation_result_for_general_metadata_fields() -> None:
    lines = format_adult_metadata_lines(
        {
            "read_only_adult_display_id": "SSIS-842",
            "read_only_adult_source_site": "avmoo.shop",
            "read_only_adult_title": "SSIS-842 彼女のリアルで生々しい姿をお見せします",
            "read_only_adult_overview": "日本語のあらすじです。欲望と嫉妬が交差する。",  # pragma: allowlist secret
            "read_only_adult_series": "リアルSEXドキュメント",
            "read_only_adult_maker": "エスワン ナンバーワンスタイル",
            "read_only_adult_label": "S1 NO.1 STYLE",
            "read_only_adult_director": "苺原",
            "read_only_adult_actors": ("うんぱい",),
            "adult_translation_title_zh": "SSIS-842 让你看到她真实而鲜活的一面",
            "adult_translation_overview_zh": "这是一段翻译后的中文简介，欲望与嫉妒在关系里彼此交错。",
            "adult_translation_series_zh": "真实性爱纪录",
            "adult_translation_maker_zh": "S1 顶级风格",
            "adult_translation_label_zh": "S1 NO.1 STYLE",
            "adult_translation_director_zh": "莓原",
        }
    )

    assert (
        "标准信息: 标题: SSIS-842 让你看到她真实而鲜活的一面 | "
        "原名: SSIS-842 彼女のリアルで生々しい姿をお見せします"
    ) in lines
    assert "简介: 这是一段翻译后的中文简介，欲望与嫉妒在关系里彼此交错。" in lines
    assert (
        "制作信息: 制作商: S1 顶级风格 | 厂牌: S1 NO.1 STYLE | "
        "系列: 真实性爱纪录 | 原系列: リアルSEXドキュメント | "
        "导演: 莓原 | 演员: うんぱい（中文名未确认）"
    ) in lines


def test_format_adult_metadata_lines_does_not_blind_translate_unknown_actors() -> None:
    lines = format_adult_metadata_lines(
        {
            "read_only_adult_display_id": "SSIS-999",
            "read_only_adult_source_site": "avmoo.shop",
            "read_only_adult_title": "SSIS-999 テスト作品",
            "read_only_adult_actors": ("架空りり",),
        }
    )

    assert any("演员: 架空りり（中文名未确认）" in line for line in lines)
    assert not any("演员: 架空莉莉" in line for line in lines)


def test_format_adult_metadata_lines_prefers_source_localized_fields_before_translation_result() -> None:
    lines = format_adult_metadata_lines(
        {
            "read_only_adult_display_id": "SSIS-842",
            "read_only_adult_title": "SSIS-842 原始日文标题",
            "read_only_adult_title_zh": "SSIS-842 来源中文标题",
            "adult_translation_title_zh": "SSIS-842 机器翻译标题",
            "read_only_adult_series": "原始系列",
            "read_only_adult_series_zh": "来源中文系列",
            "adult_translation_series_zh": "机器翻译系列",
        }
    )

    assert "标准信息: 标题: SSIS-842 来源中文标题 | 原名: SSIS-842 原始日文标题" in lines
    assert "制作信息: 系列: 来源中文系列 | 原系列: 原始系列" in lines
