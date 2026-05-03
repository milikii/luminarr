from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass

from app.services.search_reply_formatter import get_media_candidate_confirmation_action_lines

TELEGRAM_MOVIE_CARD_HEADER_TEXT = "电影海报卡片"
TELEGRAM_SEARCH_RESULT_PREFIX = "搜索结果："
TELEGRAM_MEDIA_CANDIDATE_PREFIX = "候选作品："
TELEGRAM_ADULT_BT_RESULT_PREFIX = "成人资源候选："
TELEGRAM_ADD_APPROVAL_PREFIX = "下载待确认："
TELEGRAM_ADD_APPROVAL_TASK_REF_PREFIX = "选择序号:"
TELEGRAM_IMPORT_APPROVAL_PREFIX = "导入待确认："
TELEGRAM_IMPORT_APPROVAL_TASK_ID_PREFIX = "任务 ID:"
TELEGRAM_IMPORT_APPROVAL_TASK_HASH_PREFIX = "任务 Hash:"


def format_telegram_reply(text: str) -> str:
    return _format_telegram_import_approval_reply(
        _format_telegram_add_approval_reply(
            _format_telegram_adult_bt_reply(_format_telegram_media_candidate_reply(_format_telegram_search_reply(text)))
        )
    )


def _format_telegram_search_reply(text: str) -> str:
    stripped_text = text.strip()
    if (
        not stripped_text
        or TELEGRAM_MOVIE_CARD_HEADER_TEXT not in stripped_text
        or TELEGRAM_SEARCH_RESULT_PREFIX not in stripped_text
    ):
        return text

    sections = re.split(r"\n\s*\n", stripped_text)
    card_section = next(
        (section for section in sections if section.startswith(TELEGRAM_MOVIE_CARD_HEADER_TEXT)),
        "",
    )
    result_section = next(
        (section for section in sections if section.startswith(TELEGRAM_SEARCH_RESULT_PREFIX)),
        "",
    )
    if not card_section or not result_section:
        return text

    card_lines = [line.strip() for line in card_section.splitlines() if line.strip()]
    result_lines = [line.strip() for line in result_section.splitlines() if line.strip()]
    if len(card_lines) < 2 or len(result_lines) < 2:
        return text

    query = result_lines[0].removeprefix(TELEGRAM_SEARCH_RESULT_PREFIX).strip()
    candidate_count = sum(1 for line in result_lines[1:] if re.match(r"^\d+\.\s", line))
    if candidate_count <= 0:
        return text

    formatted_lines = ["【电影卡片】", *card_lines[1:], "", f"【搜索结果】 {query}".rstrip()]
    formatted_lines.extend(result_lines[1:])
    formatted_lines.extend(("", _format_telegram_selection_hint(candidate_count)))
    return "\n".join(formatted_lines)


_MAGNET_URI_RE = re.compile(r"magnet:\?[^\s<]+")
_MAGNET_BT_HASH_RE = re.compile(r"magnet:\?xt=urn:btih:(?P<hash>[^&\s<]+)", re.IGNORECASE)


def _apply_telegram_html(line: str) -> str:
    parts: list[str] = []
    last_end = 0
    for match in _MAGNET_URI_RE.finditer(line):
        parts.append(_html.escape(line[last_end : match.start()]))
        parts.append(f"<code>{_html.escape(_shorten_magnet_uri(match.group(0)))}</code>")
        last_end = match.end()
    parts.append(_html.escape(line[last_end:]))
    return "".join(parts)


def _has_telegram_html(text: str) -> bool:
    return bool(re.search(r"<(b|i|u|s|code|pre|a)\b[^>]*>", text))


def _format_telegram_adult_bt_reply(text: str) -> str:
    stripped_text = text.strip()
    if not stripped_text.startswith(TELEGRAM_ADULT_BT_RESULT_PREFIX):
        return text

    lines = [line.rstrip() for line in stripped_text.splitlines() if line.strip()]
    if len(lines) < 2:
        return text

    query = lines[0].removeprefix(TELEGRAM_ADULT_BT_RESULT_PREFIX).strip()
    candidate_count = sum(1 for line in lines[1:] if re.match(r"^\d+\.\s", line.strip()))
    if not query or candidate_count <= 0:
        return text

    parsed_candidates = _parse_adult_bt_candidates(lines[1:])
    if not parsed_candidates:
        return text
    return _render_adult_bt_poster_caption_reply(query=query, candidates=parsed_candidates)


@dataclass(slots=True)
class _TelegramAdultBtCandidate:
    index: int
    title: str
    site: str = ""
    provider: str = ""
    seeders: str = ""
    size: str = ""
    content_id: str = ""
    category: str = ""
    detail_url: str = ""
    poster_url: str = ""
    metadata_title: str = ""
    release_date: str = ""
    runtime: str = ""
    overview: str = ""
    maker: str = ""
    label: str = ""
    series: str = ""
    director: str = ""
    actors: str = ""
    metadata_source: str = ""
    magnet: str = ""
    history_text: str = ""
    original_title: str = ""


def _parse_adult_bt_candidates(lines: list[str]) -> list[_TelegramAdultBtCandidate]:
    candidates: list[_TelegramAdultBtCandidate] = []
    current: _TelegramAdultBtCandidate | None = None
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("链接参考:") or line.startswith("只读说明：") or line.startswith("如需走成人下载链"):
            continue
        candidate_match = re.match(r"^(?P<index>\d+)\.\s+(?P<title>.+)$", line)
        if candidate_match is not None:
            current = _TelegramAdultBtCandidate(
                index=int(str(candidate_match.group("index") or "0")),
                title=str(candidate_match.group("title") or "").strip(),
            )
            candidates.append(current)
            continue
        if current is None:
            continue
        _apply_adult_bt_candidate_line(current, line)
    return candidates


def _apply_adult_bt_candidate_line(candidate: _TelegramAdultBtCandidate, line: str) -> None:
    if line.startswith("站点:"):
        parts = _parse_telegram_field_parts(line)
        candidate.site = parts.get("站点", candidate.site)
        candidate.provider = parts.get("来源入口", candidate.provider)
        candidate.seeders = parts.get("做种", candidate.seeders)
        candidate.size = parts.get("大小", candidate.size)
        return
    if line.startswith("番号:"):
        parts = _parse_telegram_field_parts(line)
        candidate.content_id = parts.get("番号", candidate.content_id)
        candidate.category = parts.get("分类", candidate.category)
        return
    if line.startswith("只读补全:"):
        parts = _parse_telegram_field_parts(line)
        candidate.metadata_source = parts.get("只读补全", candidate.metadata_source)
        candidate.content_id = parts.get("番号", candidate.content_id)
        candidate.category = parts.get("分类", candidate.category)
        return
    if line.startswith("只读标题:"):
        candidate.metadata_title = line.removeprefix("只读标题:").strip()
        return
    if line.startswith("只读详情:"):
        candidate.detail_url = line.removeprefix("只读详情:").strip()
        return
    if line.startswith("海报:"):
        candidate.poster_url = line.removeprefix("海报:").strip()
        return
    if line.startswith("标准信息:"):
        parts = _parse_telegram_field_parts(line.removeprefix("标准信息:").strip())
        candidate.metadata_title = parts.get("标题", candidate.metadata_title)
        candidate.original_title = parts.get("原名", candidate.original_title)
        candidate.release_date = parts.get("发行日", candidate.release_date)
        candidate.runtime = parts.get("时长", candidate.runtime)
        return
    if line.startswith("简介:"):
        candidate.overview = line.removeprefix("简介:").strip()
        return
    if line.startswith("制作信息:"):
        parts = _parse_telegram_field_parts(line.removeprefix("制作信息:").strip())
        candidate.maker = parts.get("制作商", candidate.maker)
        candidate.label = parts.get("厂牌", candidate.label)
        candidate.series = parts.get("系列", candidate.series)
        candidate.director = parts.get("导演", candidate.director)
        candidate.actors = parts.get("演员", candidate.actors)
        return
    if line.startswith("Metadata源:"):
        parts = _parse_telegram_field_parts(line)
        candidate.metadata_source = parts.get("Metadata源", candidate.metadata_source)
        return
    if line.startswith("磁力链接:"):
        candidate.magnet = _shorten_magnet_uri(line.removeprefix("磁力链接:").strip())
        return
    if line.startswith("资源链接:"):
        value = line.removeprefix("资源链接:").strip()
        candidate.magnet = _shorten_magnet_uri(value) if value.lower().startswith("magnet:?") else value
        return
    if line.startswith("历史:"):
        candidate.history_text = line


def _parse_telegram_field_parts(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_part in line.split("|"):
        key, separator, value = raw_part.partition(":")
        if not separator:
            continue
        cleaned_key = key.strip()
        cleaned_value = value.strip()
        if cleaned_key and cleaned_value:
            fields[cleaned_key] = cleaned_value
    return fields


def _render_adult_bt_poster_caption_reply(*, query: str, candidates: list[_TelegramAdultBtCandidate]) -> str:
    primary = candidates[0]
    display_id = primary.content_id or query
    detail_url = _first_non_empty(candidate.detail_url for candidate in candidates)
    detail_source = _format_detail_source_label(primary.metadata_source or detail_url)
    first_magnet = _first_non_empty(candidate.magnet for candidate in candidates)
    lines = [_apply_telegram_html(f"【成人资源候选】 {query}".rstrip())]
    if primary.poster_url:
        lines.append(f"海报: {primary.poster_url}")
    lines.extend(_render_adult_caption_lines(primary, display_id=display_id))
    lines.extend(("", "━━━━━━━━━━━━━━━━━━", "💾 <b>资源列表 (点击代码块一键复制)：</b>", ""))
    for candidate in candidates:
        lines.extend(_render_adult_resource_lines(candidate))
        lines.append("")
    if lines and not lines[-1]:
        lines.pop()
    action_lines = _render_adult_action_lines(
        detail_url=detail_url,
        detail_source=detail_source,
        first_magnet=first_magnet,
    )
    if action_lines:
        lines.extend(("", "下一步", *action_lines))
    return "\n".join(lines)


def _render_adult_caption_lines(candidate: _TelegramAdultBtCandidate, *, display_id: str) -> list[str]:
    title = candidate.metadata_title or candidate.title
    lines = [f"🎬 <b>{_html.escape(_format_adult_title(display_id=display_id, title=title))}</b>"]
    subtitle = _resolve_adult_subtitle(candidate, title=title)
    if subtitle:
        lines.append(f"<i>{_html.escape(subtitle)}</i>")
    lines.append("━━━━━━━━━━━━━━━━━━")
    metadata_lines = [
        _format_adult_metadata_caption_line("👤", "演员", candidate.actors, code_style=True),
        _format_adult_metadata_caption_line("🏢", "片商", candidate.maker),
        _format_adult_metadata_caption_line("🏷", "系列", candidate.series),
        _format_adult_date_runtime_line(candidate),
        _format_adult_metadata_caption_line("📦", "分类", _format_adult_category_label(candidate.category)),
    ]
    lines.extend(line for line in metadata_lines if line)
    return lines


def _render_adult_resource_lines(candidate: _TelegramAdultBtCandidate) -> list[str]:
    source_label = _format_adult_resource_source_label(candidate)
    lines = [f"<b>【资源 {candidate.index}】 {_html.escape(source_label)}</b>"]
    if candidate.magnet:
        lines.extend(
            (
                "🧲 磁力链接 (点击下方一键复制)：",
                f"<code>{_html.escape(_shorten_magnet_uri(candidate.magnet))}</code>",
            )
        )
    if candidate.history_text:
        lines.append(_html.escape(candidate.history_text))
    return lines


def _format_adult_title(*, display_id: str, title: str) -> str:
    cleaned_id = display_id.strip()
    cleaned_title = title.strip()
    if not cleaned_id:
        return cleaned_title
    if not cleaned_title:
        return f"[{cleaned_id}]"
    title_without_id = re.sub(rf"^\s*{re.escape(cleaned_id)}\s*", "", cleaned_title, flags=re.IGNORECASE).strip()
    return f"[{cleaned_id}] {title_without_id or cleaned_title}"


def _resolve_adult_subtitle(candidate: _TelegramAdultBtCandidate, *, title: str) -> str:
    if candidate.original_title and candidate.original_title != title:
        return candidate.original_title
    if not candidate.title or candidate.title == title:
        return ""
    if candidate.title.lower().startswith((candidate.content_id or "").lower()):
        return ""
    return candidate.title


def _format_adult_metadata_caption_line(icon: str, label: str, value: str, *, code_style: bool = False) -> str:
    cleaned_value = value.strip()
    if not cleaned_value:
        return ""
    rendered_value = _html.escape(cleaned_value)
    if code_style:
        rendered_value = f"<code>{rendered_value}</code>"
    return f"{icon} <b>{label}：</b> {rendered_value}"


def _format_adult_date_runtime_line(candidate: _TelegramAdultBtCandidate) -> str:
    parts: list[str] = []
    if candidate.release_date:
        parts.append(f"📅 <b>日期：</b> {_html.escape(candidate.release_date)}")
    if candidate.runtime:
        parts.append(f"⏳ <b>时长：</b> {_html.escape(candidate.runtime)}")
    return "  |  ".join(parts)


def _format_adult_category_label(category: str) -> str:
    normalized = category.strip().lower()
    if normalized == "censored":
        return "有码 (Censored)"
    if normalized == "uncensored":
        return "无码 (Uncensored)"
    return category.strip()


def _format_adult_resource_source_label(candidate: _TelegramAdultBtCandidate) -> str:
    site = candidate.site or candidate.provider or "unknown"
    title_prefix = ""
    title_prefix_match = re.match(r"^\s*(\[[^\]]+\])", candidate.title)
    if title_prefix_match is not None:
        title_prefix = f"{title_prefix_match.group(1)} "
    parts = [f"{title_prefix}{site}".strip()]
    if candidate.size:
        parts.append(candidate.size)
    if candidate.seeders:
        parts.append(f"做种: {candidate.seeders}")
    return " | ".join(parts)


def _render_adult_action_lines(*, detail_url: str, detail_source: str, first_magnet: str) -> list[str]:
    lines: list[str] = []
    if detail_url:
        lines.append(f"🌐 查看详情 ({detail_source})：打开 {detail_url}")
    if first_magnet:
        lines.append(f"➡️ 下一步：发送 {_shorten_magnet_uri(first_magnet)}")
    return lines


def _format_detail_source_label(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return "详情"
    match = re.search(r"https?://(?:www\.)?([^/]+)", cleaned)
    if match is not None:
        cleaned = match.group(1)
    return cleaned.split(".")[0] or "详情"


def _first_non_empty(values) -> str:
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned:
            return cleaned
    return ""


def _shorten_magnet_uri(value: str) -> str:
    match = _MAGNET_BT_HASH_RE.search(value.strip())
    if match is None:
        return value.strip()
    return f"magnet:?xt=urn:btih:{match.group('hash').lower()}"


def _truncate_text(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return f"{value[: limit - 3]}..."


def _split_candidate_field(line: str) -> tuple[str, str]:
    for label in ("海报", "原名", "年份", "类型", "简介", "TMDB详情"):
        for separator in ("：", ":"):
            prefix = f"{label}{separator}"
            if line.startswith(prefix):
                return label, line.removeprefix(prefix).strip()
    return "", ""


def _format_telegram_media_candidate_detail_line(line: str) -> str:
    label, value = _split_candidate_field(line)
    if not label:
        return _apply_telegram_html(line)
    if label == "海报":
        return f"海报: {value}"
    if label == "原名":
        return f"<i>{_html.escape(value)}</i>"
    if label == "年份":
        return f"📅 <b>年份：</b> {_html.escape(value)}"
    if label == "类型":
        return f"🎞 <b>类型：</b> {_html.escape(value)}"
    if label == "简介":
        return f"📝 <b>简介：</b> {_html.escape(value)}"
    if label == "TMDB详情":
        return f"🌐 <b>TMDB详情：</b> {_html.escape(value)}"
    return _apply_telegram_html(line)


@dataclass(slots=True)
class _TelegramMediaCandidate:
    index: int
    title: str
    poster_url: str = ""
    original_title: str = ""
    year: str = ""
    media_type: str = ""
    overview: str = ""
    tmdb_detail_url: str = ""


def _format_telegram_media_candidate_reply(text: str) -> str:
    stripped_text = text.strip()
    if not stripped_text.startswith(TELEGRAM_MEDIA_CANDIDATE_PREFIX):
        return text

    lines = [line.rstrip() for line in stripped_text.splitlines() if line.strip()]
    if len(lines) < 2:
        return text

    query = _strip_delivery_status_marker(lines[0].removeprefix(TELEGRAM_MEDIA_CANDIDATE_PREFIX).strip())
    candidates = _parse_telegram_media_candidates(lines[1:])
    candidate_count = len(candidates)
    if not query or candidate_count <= 0:
        return text

    formatted_lines = [f"【{_html.escape(query)}】共找到 {candidate_count} 条相关信息，请选择操作"]
    for candidate in candidates:
        formatted_lines.append("")
        formatted_lines.extend(_render_telegram_media_candidate_block(candidate))
    formatted_lines.extend(("", "下一步", *get_media_candidate_confirmation_action_lines()))
    return "\n".join(formatted_lines)


def _parse_telegram_media_candidates(lines: list[str]) -> list[_TelegramMediaCandidate]:
    candidates: list[_TelegramMediaCandidate] = []
    current: _TelegramMediaCandidate | None = None
    for raw_line in lines:
        cleaned_line = raw_line.strip()
        if not cleaned_line or cleaned_line == "下一步":
            continue
        if cleaned_line.startswith(("确认作品：", "都不对：", "候选作品（")):
            continue
        candidate_match = re.match(r"^(?P<index>\d+)\.\s+(?P<title>.+)$", cleaned_line)
        if candidate_match is not None:
            current = _TelegramMediaCandidate(
                index=int(str(candidate_match.group("index") or "0")),
                title=str(candidate_match.group("title") or "").strip(),
            )
            candidates.append(current)
            continue
        if current is not None:
            _apply_telegram_media_candidate_line(current, cleaned_line)
    return candidates


def _apply_telegram_media_candidate_line(candidate: _TelegramMediaCandidate, line: str) -> None:
    label, value = _split_candidate_field(line)
    if not label or not value:
        return
    if label == "海报":
        candidate.poster_url = value
        return
    if label == "原名":
        candidate.original_title = value
        return
    if label == "年份":
        candidate.year = value
        return
    if label == "类型":
        candidate.media_type = value
        return
    if label == "简介":
        candidate.overview = value
        return
    if label == "TMDB详情":
        candidate.tmdb_detail_url = value


def _render_telegram_media_candidate_block(candidate: _TelegramMediaCandidate) -> list[str]:
    lines = [_render_telegram_media_candidate_title_line(candidate)]
    if candidate.index == 1 and candidate.poster_url:
        poster_url = _html.escape(candidate.poster_url, quote=True)
        lines.append(f'海报预览：<a href="{poster_url}">打开海报</a>')
    if candidate.original_title:
        lines.append(f"<i>{_html.escape(candidate.original_title)}</i>")
    if candidate.year:
        lines.append(f"📅 <b>年份：</b> {_html.escape(candidate.year)}")
    if candidate.media_type:
        lines.append(f"🎞 <b>类型：</b> {_html.escape(candidate.media_type)}")
    if candidate.overview:
        lines.append(f"📝 <b>简介：</b> {_html.escape(candidate.overview)}")
    return lines


def _render_telegram_media_candidate_title_line(candidate: _TelegramMediaCandidate) -> str:
    if not candidate.tmdb_detail_url:
        return _html.escape(f"{candidate.index}. {candidate.title}")
    tmdb_detail_url = _html.escape(candidate.tmdb_detail_url, quote=True)
    return f'{candidate.index}. <a href="{tmdb_detail_url}">{_html.escape(candidate.title)}</a>'


def _format_telegram_adult_bt_line(line: str) -> str:
    if line.startswith("海报:"):
        return line
    if line.startswith("磁力链接:"):
        raw = line.replace("磁力链接:", "磁力:", 1).strip()
        return _apply_telegram_html(raw)
    if line.startswith("资源链接:"):
        raw = line.replace("资源链接:", "链接:", 1).strip()
        return _apply_telegram_html(raw)
    if line.startswith("只读详情:"):
        return _apply_telegram_html(line.replace("只读详情:", "详情:", 1).strip())
    metadata_match = re.match(r"^Metadata源:\s*(?P<source>[^|]+?)(?:\s*\|\s*角色:\s*(?P<role>.+))?$", line)
    if metadata_match is not None:
        source = str(metadata_match.group("source") or "").strip()
        role = str(metadata_match.group("role") or "").strip()
        if role == "backup_cross_check":
            role = "backup/cross-check"
        if role:
            return _apply_telegram_html(f"信息源: {source}（{role}）")
        return _apply_telegram_html(f"信息源: {source}")
    if line.startswith("标准信息:"):
        return _apply_telegram_html(line.removeprefix("标准信息:").strip())
    if line.startswith("制作信息:"):
        return _apply_telegram_html(line.removeprefix("制作信息:").strip().replace(", ", " / "))
    return _apply_telegram_html(line)


def _is_adult_metadata_line(line: str) -> bool:
    metadata_prefixes = (
        "海报:",
        "番号:",
        "只读补全:",
        "只读标题:",
        "详情:",
        "标题:",
        "发行日:",
        "时长:",
        "制作商:",
        "厂牌:",
        "系列:",
        "导演:",
        "演员:",
        "信息源:",
    )
    return line.startswith(metadata_prefixes)


def _order_adult_metadata_lines(lines: list[str]) -> list[str]:
    ordering = {
        "海报:": 0,
        "番号:": 1,
        "只读补全:": 2,
        "只读标题:": 3,
        "标题:": 4,
        "发行日:": 5,
        "时长:": 6,
        "制作商:": 7,
        "厂牌:": 8,
        "系列:": 9,
        "导演:": 10,
        "演员:": 11,
        "详情:": 12,
        "信息源:": 13,
    }
    return sorted(lines, key=lambda line: ordering.get(_resolve_line_prefix(line), 99))


def _resolve_line_prefix(line: str) -> str:
    for prefix in (
        "海报:",
        "番号:",
        "只读补全:",
        "只读标题:",
        "标题:",
        "发行日:",
        "时长:",
        "制作商:",
        "厂牌:",
        "系列:",
        "导演:",
        "演员:",
        "详情:",
        "信息源:",
    ):
        if line.startswith(prefix):
            return prefix
    return ""


def _strip_delivery_status_marker(value: str) -> str:
    return re.sub(r"\s+[✓❌⏳⚠️]+$", "", value).strip()


def _format_telegram_selection_hint(candidate_count: int) -> str:
    if candidate_count <= 1:
        return "直接回复 1 继续，例如：1"
    return f"直接回复 1-{candidate_count} 中的序号继续，例如：1"


def _format_telegram_add_approval_reply(text: str) -> str:
    stripped_text = text.strip()
    if not stripped_text.startswith(TELEGRAM_ADD_APPROVAL_PREFIX):
        return text

    lines = [line.strip() for line in stripped_text.splitlines() if line.strip()]
    if len(lines) < 3:
        return text

    title = lines[0].removeprefix(TELEGRAM_ADD_APPROVAL_PREFIX).strip()
    task_ref = lines[1].removeprefix(TELEGRAM_ADD_APPROVAL_TASK_REF_PREFIX).strip()
    confirm_line = lines[2]
    expected_confirm = f"confirm {task_ref}"
    if not title or not task_ref or expected_confirm not in confirm_line:
        return text

    return "\n".join(
        [
            "【下载审批】",
            f"标题: {title}",
            f"选择序号: {task_ref}",
            f"确认命令: {expected_confirm}",
            "",
            f"直接回复 {expected_confirm} 执行下载",
        ]
    )


def _format_telegram_import_approval_reply(text: str) -> str:
    stripped_text = text.strip()
    if not stripped_text.startswith(TELEGRAM_IMPORT_APPROVAL_PREFIX):
        return text

    lines = [line.strip() for line in stripped_text.splitlines() if line.strip()]
    if len(lines) < 4:
        return text

    name = lines[0].removeprefix(TELEGRAM_IMPORT_APPROVAL_PREFIX).strip()
    task_id = lines[1].removeprefix(TELEGRAM_IMPORT_APPROVAL_TASK_ID_PREFIX).strip()
    task_hash = lines[2].removeprefix(TELEGRAM_IMPORT_APPROVAL_TASK_HASH_PREFIX).strip()
    confirm_line = lines[3]
    confirm_match = re.match(r"^请发送\s+(confirm\s+.+?)\s+执行导入。?$", confirm_line)
    if not name or not task_id or not task_hash or confirm_match is None:
        return text

    confirm_command = confirm_match.group(1).strip()
    return "\n".join(
        [
            "【导入审批】",
            f"资源: {name}",
            f"任务 ID: {task_id}",
            f"任务 Hash: {task_hash}",
            f"确认命令: {confirm_command}",
            "",
            "下一步",
            f"确认导入：发送 {confirm_command}",
        ]
    )
