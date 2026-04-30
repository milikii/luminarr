from __future__ import annotations

from dataclasses import dataclass
import re


_STATUS_EMOJI = {
    "success": "✓",
    "failure": "❌",
    "pending": "⏳",
    "warning": "⚠️",
}


@dataclass(frozen=True, slots=True)
class DeliveryHeader:
    kind: str
    title: str
    subtitle: str | None = None


@dataclass(frozen=True, slots=True)
class DeliverySection:
    label: str | None
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeliveryAction:
    label: str
    hint: str
    kind: str
    callback_query: str | None = None


@dataclass(frozen=True, slots=True)
class DeliveryItem:
    header: DeliveryHeader
    sections: tuple[DeliverySection, ...]
    actions: tuple[DeliveryAction, ...]
    footer: str | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class _RenderStyle:
    title_wrapper: tuple[str, str] = ("", "")
    section_prefix: str = ""
    action_prefix: str = ""
    action_separator: str = "："
    blank_line_between_sections: bool = True


class TelegramDeliveryText(str):
    """Telegram text payload that preserves inline action metadata."""

    __slots__ = ("actions",)

    def __new__(cls, value: str, actions: tuple[DeliveryAction, ...]):
        instance = super().__new__(cls, value)
        instance.actions = actions
        return instance


def render_telegram_text(item: DeliveryItem) -> str:
    text = _render_text_item(item, _RenderStyle())
    return TelegramDeliveryText(text, tuple(_materialize_telegram_action(action) for action in item.actions))


def render_feishu_text(item: DeliveryItem) -> str:
    return _render_text_item(item, _RenderStyle())


def render_personal_wechat_text(item: DeliveryItem) -> str:
    return _render_text_item(
        item,
        _RenderStyle(
            title_wrapper=("【", "】"),
            section_prefix="▸ ",
        ),
    )


def render_wecom_text(item: DeliveryItem) -> str:
    return _render_text_item(
        item,
        _RenderStyle(
            section_prefix="- ",
            action_prefix="- ",
            blank_line_between_sections=False,
        ),
    )


def render_delivery_item(item: DeliveryItem, *, channel: str) -> str:
    channel_name = channel.strip().lower()
    if channel_name == "personal_wechat":
        return render_personal_wechat_text(item)
    if channel_name == "wecom":
        return render_wecom_text(item)
    if channel_name == "feishu":
        return render_feishu_text(item)
    return render_telegram_text(item)


def extract_telegram_actions(text: str) -> tuple[DeliveryAction, ...]:
    actions = getattr(text, "actions", ())
    if not isinstance(actions, tuple):
        return ()
    normalized: list[DeliveryAction] = []
    for action in actions:
        if not isinstance(action, DeliveryAction):
            return ()
        normalized.append(action)
    return tuple(normalized)


def _render_text_item(item: DeliveryItem, style: _RenderStyle) -> str:
    lines: list[str] = []
    header_line = _format_header_line(item.header, status=item.status, style=style)
    if header_line:
        lines.append(header_line)
    if item.header.subtitle:
        lines.append(item.header.subtitle.strip())

    section_blocks = [_format_section(section=section, style=style) for section in item.sections]
    section_blocks = [block for block in section_blocks if block]
    if section_blocks:
        if lines:
            lines.append("")
        lines.extend(_join_blocks(section_blocks, insert_blank_line=style.blank_line_between_sections))

    action_block = _format_actions(item.actions, style=style)
    if action_block:
        if lines:
            lines.append("")
        lines.extend(action_block)

    if item.footer:
        footer = item.footer.strip()
        if footer:
            if lines:
                lines.append("")
            lines.append(footer)

    return "\n".join(lines).strip()


def _format_header_line(header: DeliveryHeader, *, status: str | None, style: _RenderStyle) -> str:
    title = header.title.strip()
    if not title:
        return ""
    prefix, suffix = style.title_wrapper
    text = f"{prefix}{title}{suffix}".strip()
    emoji = _STATUS_EMOJI.get((status or "").strip())
    if emoji:
        return f"{text} {emoji}".strip()
    return text


def _format_section(*, section: DeliverySection, style: _RenderStyle) -> list[str]:
    block: list[str] = []
    label = (section.label or "").strip()
    if label:
        block.append(f"{style.section_prefix}{label}".rstrip())
    for line in section.lines:
        cleaned_line = line.strip()
        if cleaned_line:
            block.append(cleaned_line)
    return block


def _format_actions(actions: tuple[DeliveryAction, ...], *, style: _RenderStyle) -> list[str]:
    if not actions:
        return []
    lines = ["下一步"]
    for action in actions:
        label = action.label.strip()
        hint = action.hint.strip()
        body = f"{label}{style.action_separator}{hint}" if hint else label
        lines.append(f"{style.action_prefix}{body}".rstrip())
    return lines


def _materialize_telegram_action(action: DeliveryAction) -> DeliveryAction:
    callback_query = _resolve_callback_query(action)
    return DeliveryAction(
        label=action.label,
        hint=action.hint,
        kind=action.kind,
        callback_query=callback_query,
    )


def _resolve_callback_query(action: DeliveryAction) -> str | None:
    explicit = (action.callback_query or "").strip()
    if explicit:
        return explicit
    hint = action.hint.strip()
    if not hint:
        return None
    match = re.match(r"^发送\s+(.+?)\s*$", hint)
    if match is not None:
        callback_query = match.group(1).strip()
        return callback_query or None
    return None


def _join_blocks(blocks: list[list[str]], *, insert_blank_line: bool) -> list[str]:
    lines: list[str] = []
    for index, block in enumerate(blocks):
        if index > 0 and insert_blank_line:
            lines.append("")
        lines.extend(block)
    return lines
