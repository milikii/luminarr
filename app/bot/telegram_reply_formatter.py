from __future__ import annotations

import re

TELEGRAM_MOVIE_CARD_HEADER_TEXT = "电影海报卡片"
TELEGRAM_SEARCH_RESULT_PREFIX = "搜索结果："
TELEGRAM_ADD_APPROVAL_PREFIX = "下载待确认："
TELEGRAM_ADD_APPROVAL_TASK_REF_PREFIX = "选择序号:"
TELEGRAM_IMPORT_APPROVAL_PREFIX = "导入待确认："
TELEGRAM_IMPORT_APPROVAL_TASK_ID_PREFIX = "任务 ID:"
TELEGRAM_IMPORT_APPROVAL_TASK_HASH_PREFIX = "任务 Hash:"


def format_telegram_reply(text: str) -> str:
    return _format_telegram_import_approval_reply(
        _format_telegram_add_approval_reply(_format_telegram_search_reply(text))
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
