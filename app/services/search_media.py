from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.clients.tmdb import TmdbMovie
from app.db.candidate_repo import CandidateMappingRepo, CandidatePayloadCorruptionError, CandidatePersistenceError
from app.db.clarification_repo import ClarificationPersistenceError, ClarificationRepo

SearchFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]
LookupMovieFunc = Callable[[str, str], Awaitable[TmdbMovie | None]]

EMPTY_QUERY_TEXT = "请输入要搜索的内容。"
NO_RESULT_TEXT_TEMPLATE = "未找到候选结果：{query}"
BT_READ_ONLY_EMPTY_QUERY_TEXT = "BT 只读探索格式：bt搜 <关键词>"
BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE = "BT 只读探索未找到候选：{query}"
BT_READ_ONLY_NOTICE_TEXT = "只读说明：当前结果仅供手动 BT 探索和站点规则排查参考，不会创建审批或下载任务。"
AMBIGUOUS_QUERY_TEXT_TEMPLATE = (
    "片名可能有多个版本：{query}\n"
    "请补充更具体信息后再搜索，例如：\n"
    "- 片名 + 年份（例如：Dune 2021）\n"
    "- 更完整片名（例如：Dune Part Two）\n"
    "只读探索参考：\n"
    "{options}"
)
AMBIGUOUS_OPTION_FALLBACK_TEXT = "- 暂无可区分候选，请直接补充年份。"
AMBIGUOUS_MIN_RESULT_COUNT = 3
AMBIGUOUS_MAX_OPTION_COUNT = 3
CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT = "搜索待澄清状态写入失败，请稍后重试。"
CANDIDATE_STATE_UNAVAILABLE_TEXT = "搜索候选状态写入失败，请稍后重试。"
CLARIFICATION_CLEAR_STATE_UNAVAILABLE_TEXT = "搜索待澄清状态清理失败，请稍后重试。"
CLARIFICATION_MISSING_AFTER_UPSERT_REASON = "clarification_state missing after upsert"
CLARIFICATION_CLEAR_RESULT_MISSING_REASON = "clarification clear result missing"
CANDIDATE_COUNT_RESULT_MISSING_AFTER_SAVE_REASON = "candidate_mapping count missing after query"
CANDIDATE_COUNT_MISMATCH_AFTER_SAVE_REASON = "candidate_mapping count mismatch after save"
CANDIDATE_CLEAR_RESULT_MISSING_REASON = "candidate clear result missing"
CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON = "candidate clear result missing during persist rollback"


@dataclass(frozen=True, slots=True)
class Candidate:
    title: str
    year: str
    quality: str
    size: str
    indexer: str


@dataclass(frozen=True, slots=True)
class ParsedMovieQuery:
    title: str
    year: str


@dataclass(frozen=True, slots=True)
class AmbiguousOption:
    title: str
    year: str


@dataclass(frozen=True, slots=True)
class ClarificationQueryLoadResult:
    query: str | None = None
    load_failed: bool = False


@dataclass(frozen=True, slots=True)
class CandidateLoadResult:
    candidate: Mapping[str, Any] | None = None
    load_failed: bool = False


class SearchMediaService:
    def __init__(
        self,
        search_func: SearchFunc,
        raw_search_func: SearchFunc | None = None,
        limit: int = 5,
        candidate_repo: CandidateMappingRepo | None = None,
        clarification_repo: ClarificationRepo | None = None,
        lookup_movie_func: LookupMovieFunc | None = None,
    ) -> None:
        self._search_func = search_func
        self._raw_search_func = raw_search_func or search_func
        self._limit = max(1, limit)
        self._candidate_repo = candidate_repo
        self._clarification_repo = clarification_repo
        self._lookup_movie_func = lookup_movie_func
        self._recent_candidates_by_chat: dict[int, list[dict[str, Any]]] = {}
        self._clarification_pending_by_chat: dict[int, str] = {}

    async def search_raw_candidates(self, query: str) -> Sequence[Mapping[str, Any]]:
        cleaned_query = query.strip()
        if not cleaned_query:
            return ()
        try:
            return await self._raw_search_func(cleaned_query)
        except Exception as error:
            print(
                f"\033[31m[BT 只读搜索失败]\033[0m query={cleaned_query} 错误={error}\n\033[33m[处理建议]\033[0m 检查 BT 搜索源、代理和网络连通性；当前只读探索没有拿到结果，且这不是正常的“无候选”状态。",
                flush=True,
            )
            raise

    async def search_bt_read_only_and_format(self, query: str) -> str:
        cleaned_query = _normalize_spaces(query)
        if not cleaned_query:
            return BT_READ_ONLY_EMPTY_QUERY_TEXT

        raw_results = await self.search_raw_candidates(cleaned_query)
        selected_raw_results = [_to_candidate_dict(item) for item in raw_results[: self._limit]]
        return format_bt_read_only_reply(cleaned_query, selected_raw_results)

    async def search_and_format(self, query: str, chat_id: int | None = None) -> str:
        cleaned_query = query.strip()
        if not cleaned_query:
            return EMPTY_QUERY_TEXT

        parsed_query = parse_movie_query(cleaned_query)
        fallback_query = _build_query(parsed_query.title, parsed_query.year)
        raw_results: Sequence[Mapping[str, Any]] = ()
        tmdb_movie: TmdbMovie | None = None

        if self._lookup_movie_func is not None:
            try:
                tmdb_movie = await self._lookup_movie_func(parsed_query.title, parsed_query.year)
            except Exception as error:
                print(
                    f"\033[31m[TMDB 查询失败]\033[0m query={cleaned_query} title={parsed_query.title} year={parsed_query.year or '-'} 错误={error}\n\033[33m[处理建议]\033[0m 检查 TMDB API、代理和网络连通性；当前会退回普通搜索，但海报卡片和标题归一化结果可能缺失。",
                    flush=True,
                )
                tmdb_movie = None
            if tmdb_movie is not None:
                resolved_year = tmdb_movie.year or parsed_query.year
                ordered_queries = _unique_queries(
                    [
                        _build_query(tmdb_movie.title, resolved_year),
                        _build_query(tmdb_movie.original_title, resolved_year),
                    ]
                )
                raw_results = await _search_candidates_with_logging(
                    search_func=self._search_func,
                    ordered_queries=ordered_queries,
                    user_query=cleaned_query,
                )
            else:
                raw_results = await _search_candidates_with_logging(
                    search_func=self._search_func,
                    ordered_queries=(fallback_query,),
                    user_query=cleaned_query,
                )
        else:
            raw_results = await _search_candidates_with_logging(
                search_func=self._search_func,
                ordered_queries=(fallback_query,),
                user_query=cleaned_query,
            )

        ambiguous_text = _format_ambiguous_clarification(
            query=cleaned_query,
            parsed_query=parsed_query,
            raw_results=raw_results,
        )
        if ambiguous_text is not None:
            if chat_id is not None and not self._set_clarification_pending(chat_id=chat_id, query=cleaned_query):
                return CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT
            return ambiguous_text

        selected_raw_results = [_to_candidate_dict(item) for item in raw_results[: self._limit]]
        if chat_id is not None:
            self._recent_candidates_by_chat[chat_id] = selected_raw_results
            if selected_raw_results:
                clarification_pending = self.is_clarification_pending(chat_id)
                if clarification_pending is None:
                    self._recent_candidates_by_chat.pop(chat_id, None)
                    return CLARIFICATION_CLEAR_STATE_UNAVAILABLE_TEXT
                if clarification_pending and not self._clear_clarification_pending(chat_id=chat_id):
                    self._recent_candidates_by_chat.pop(chat_id, None)
                    return CLARIFICATION_CLEAR_STATE_UNAVAILABLE_TEXT
            else:
                if not self._set_clarification_pending(chat_id=chat_id, query=cleaned_query):
                    self._recent_candidates_by_chat.pop(chat_id, None)
                    return CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT
            if self._candidate_repo is not None:
                try:
                    self._candidate_repo.save_candidates(chat_id, selected_raw_results)
                except CandidatePersistenceError as error:
                    if str(error) == CANDIDATE_COUNT_RESULT_MISSING_AFTER_SAVE_REASON:
                        print(
                            f"\033[31m[搜索候选写入结果缺失]\033[0m chat_id={chat_id} 错误={error}\n"
                            "\033[33m[处理建议]\033[0m 检查 candidate_mapping 写入后的计数查询是否仍带有完整结果；"
                            "当前会直接返回候选状态写入失败，避免把缺失真相误判成仍可继续按序号选择的候选缓存。",
                            flush=True,
                        )
                    elif str(error) == CANDIDATE_COUNT_MISMATCH_AFTER_SAVE_REASON:
                        print(
                            f"\033[31m[搜索候选写入后记录不一致]\033[0m chat_id={chat_id} 错误={error}\n"
                            "\033[33m[处理建议]\033[0m 检查 candidate_mapping 表是否被并发删除或部分回滚；"
                            "如需继续按序号选择，请先确认 SQLite 写入后条目数和预期一致。",
                            flush=True,
                        )
                    else:
                        print(
                            f"\033[31m[搜索候选持久化失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/候选表写入是否正常；当前会直接返回候选状态写入失败，避免把持久化真相缺口混成仍可继续按序号选择的候选缓存。",
                            flush=True,
                        )
                    self._recent_candidates_by_chat.pop(chat_id, None)
                    try:
                        cleared_result = self._candidate_repo.clear_candidates(chat_id)
                        if cleared_result is None:
                            raise CandidatePersistenceError(CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON)
                    except Exception as rollback_error:
                        if str(rollback_error) == CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON:
                            print(
                                f"\033[31m[搜索候选回滚清理结果缺失]\033[0m chat_id={chat_id} 错误={rollback_error}\n"
                                "\033[33m[处理建议]\033[0m 检查 candidate_mapping 回滚删除返回是否仍带有明确结果；"
                                "当前已按状态写入失败停路，但坏候选可能仍残留在持久化表里。",
                                flush=True,
                            )
                        else:
                            print(
                                f"\033[31m[搜索候选清理失败]\033[0m chat_id={chat_id} 错误={rollback_error}\n\033[33m[处理建议]\033[0m 检查 SQLite/候选表删除是否正常；当前已按状态写入失败停路，但坏候选可能仍残留在持久化表里。",
                                flush=True,
                            )
                    return CANDIDATE_STATE_UNAVAILABLE_TEXT
                except Exception as error:
                    print(
                        f"\033[31m[搜索候选持久化失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/候选表写入是否正常；当前会直接返回候选状态写入失败，避免把持久化真相缺口混成仍可继续按序号选择的候选缓存。",
                        flush=True,
                    )
                    self._recent_candidates_by_chat.pop(chat_id, None)
                    try:
                        cleared_result = self._candidate_repo.clear_candidates(chat_id)
                        if cleared_result is None:
                            raise CandidatePersistenceError(CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON)
                    except Exception as rollback_error:
                        if str(rollback_error) == CANDIDATE_CLEAR_RESULT_MISSING_DURING_ROLLBACK_REASON:
                            print(
                                f"\033[31m[搜索候选回滚清理结果缺失]\033[0m chat_id={chat_id} 错误={rollback_error}\n"
                                "\033[33m[处理建议]\033[0m 检查 candidate_mapping 回滚删除返回是否仍带有明确结果；"
                                "当前已按状态写入失败停路，但坏候选可能仍残留在持久化表里。",
                                flush=True,
                            )
                        else:
                            print(
                                f"\033[31m[搜索候选清理失败]\033[0m chat_id={chat_id} 错误={rollback_error}\n\033[33m[处理建议]\033[0m 检查 SQLite/候选表删除是否正常；当前已按状态写入失败停路，但坏候选可能仍残留在持久化表里。",
                                flush=True,
                            )
                    return CANDIDATE_STATE_UNAVAILABLE_TEXT

        candidates = [normalize_candidate(item) for item in selected_raw_results]
        return format_movie_query_reply(cleaned_query, parsed_query, tmdb_movie, candidates)

    def get_cached_candidate(self, chat_id: int, index: int) -> Mapping[str, Any] | None:
        return self.get_cached_candidate_load_result(chat_id, index).candidate

    def get_cached_candidate_load_result(self, chat_id: int, index: int) -> CandidateLoadResult:
        if index < 1:
            return CandidateLoadResult()
        candidates = self._recent_candidates_by_chat.get(chat_id)
        resolved_index = index - 1
        if candidates and resolved_index < len(candidates):
            return CandidateLoadResult(candidate=candidates[resolved_index])

        return self._load_persisted_candidate(chat_id=chat_id, index=index)

    def has_cached_candidates(self, chat_id: int) -> bool | None:
        if chat_id <= 0:
            return False
        candidates = self._recent_candidates_by_chat.get(chat_id)
        if candidates:
            return True
        load_result = self._load_persisted_candidate(chat_id=chat_id, index=1)
        if load_result.load_failed:
            return None
        return load_result.candidate is not None

    def clear_cached_candidates(self, chat_id: int) -> bool:
        if chat_id <= 0:
            return False

        cleared = False
        previous_candidates: Sequence[Mapping[str, Any]] | None = None
        if chat_id in self._recent_candidates_by_chat:
            previous_candidates = tuple(self._recent_candidates_by_chat[chat_id])
            self._recent_candidates_by_chat.pop(chat_id, None)
            cleared = True
        cleared = self._clear_clarification_pending(chat_id=chat_id) or cleared

        if self._candidate_repo is None:
            return cleared
        try:
            cleared_result = self._candidate_repo.clear_candidates(chat_id)
            if cleared_result is None:
                raise CandidatePersistenceError(CANDIDATE_CLEAR_RESULT_MISSING_REASON)
            return cleared_result or cleared
        except Exception as error:
            if str(error) == CANDIDATE_CLEAR_RESULT_MISSING_REASON:
                print(
                    f"\033[31m[搜索候选清理结果缺失]\033[0m chat_id={chat_id} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 candidate_mapping 删除返回是否仍带有明确结果；"
                    "当前进程内候选已清掉，但重启后旧候选可能仍残留。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[搜索候选清理失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/候选表删除是否正常；当前进程内候选已清掉，但重启后旧候选可能仍残留。",
                    flush=True,
                )
            if previous_candidates is not None:
                self._recent_candidates_by_chat[chat_id] = list(previous_candidates)
            return False

    def is_clarification_pending(self, chat_id: int) -> bool | None:
        if chat_id <= 0:
            return False
        if chat_id in self._clarification_pending_by_chat:
            return True
        load_result = self._load_persisted_clarification_query(chat_id=chat_id)
        if load_result.load_failed:
            return None
        if load_result.query is None:
            return False
        self._clarification_pending_by_chat[chat_id] = load_result.query
        return True

    def clear_clarification_pending(self, chat_id: int) -> bool:
        if chat_id <= 0:
            return False
        return self._clear_clarification_pending(chat_id=chat_id)

    def _set_clarification_pending(self, *, chat_id: int, query: str) -> bool:
        if chat_id <= 0:
            return False
        previous_query = self._clarification_pending_by_chat.get(chat_id, "")
        self._clarification_pending_by_chat[chat_id] = query
        if self._clarification_repo is None:
            return True
        try:
            self._clarification_repo.upsert_pending(chat_id=chat_id, query=query)
        except ClarificationPersistenceError as error:
            if str(error) == CLARIFICATION_MISSING_AFTER_UPSERT_REASON:
                print(
                    f"\033[31m[搜索澄清态写入后记录缺失]\033[0m chat_id={chat_id} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 clarification_state 表是否被并发删除或触发器回滚；"
                    "如需继续待澄清流程，请先确认 SQLite 写入后能立即回读该记录。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[搜索澄清态持久化失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/clarification 表写入是否正常；当前进程内仍保留待澄清状态，但重启后可能丢失这次待确认查询。",
                    flush=True,
                )
            if previous_query:
                self._clarification_pending_by_chat[chat_id] = previous_query
            else:
                self._clarification_pending_by_chat.pop(chat_id, None)
            return False
        except Exception as error:
            print(
                f"\033[31m[搜索澄清态持久化失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/clarification 表写入是否正常；当前进程内仍保留待澄清状态，但重启后可能丢失这次待确认查询。",
                flush=True,
            )
            if previous_query:
                self._clarification_pending_by_chat[chat_id] = previous_query
            else:
                self._clarification_pending_by_chat.pop(chat_id, None)
            return False
        return True

    def _clear_clarification_pending(self, *, chat_id: int) -> bool:
        cleared = False
        previous_query = ""
        if chat_id in self._clarification_pending_by_chat:
            previous_query = self._clarification_pending_by_chat[chat_id]
            self._clarification_pending_by_chat.pop(chat_id, None)
            cleared = True
        if self._clarification_repo is None:
            return cleared
        try:
            cleared_result = self._clarification_repo.clear_pending(chat_id=chat_id)
            if cleared_result is None:
                raise ClarificationPersistenceError(CLARIFICATION_CLEAR_RESULT_MISSING_REASON)
            return cleared_result or cleared
        except Exception as error:
            if str(error) == CLARIFICATION_CLEAR_RESULT_MISSING_REASON:
                print(
                    f"\033[31m[搜索澄清态清理结果缺失]\033[0m chat_id={chat_id} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 clarification 表删除返回是否仍带有明确结果；"
                    "当前进程内待澄清状态已清掉，但重启后旧查询可能仍残留。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[搜索澄清态清理失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/clarification 表删除是否正常；当前进程内待澄清状态已清掉，但重启后旧查询可能仍残留。",
                    flush=True,
                )
            if previous_query:
                self._clarification_pending_by_chat[chat_id] = previous_query
            return False

    def _load_persisted_clarification_query(self, *, chat_id: int) -> ClarificationQueryLoadResult:
        if self._clarification_repo is None:
            return ClarificationQueryLoadResult()
        try:
            return ClarificationQueryLoadResult(
                query=self._clarification_repo.get_pending_query(chat_id=chat_id),
            )
        except Exception as error:
            print(
                f"\033[31m[搜索澄清态读取失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/clarification 表读取是否正常；当前相关入口会按状态不可用处理，避免把持久化异常误判成“无待澄清记录”。",
                flush=True,
            )
            return ClarificationQueryLoadResult(load_failed=True)

    def _load_persisted_candidate(self, *, chat_id: int, index: int) -> CandidateLoadResult:
        if self._candidate_repo is None:
            return CandidateLoadResult()
        try:
            return CandidateLoadResult(candidate=self._candidate_repo.get_candidate(chat_id, index))
        except CandidatePayloadCorruptionError as error:
            print(
                f"\033[31m[搜索候选载荷损坏]\033[0m chat_id={chat_id} index={index} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/candidate_mapping 表里的 candidate_json 是否仍是合法 JSON；当前相关入口会按候选读取失败或状态不可用处理，避免把持久化坏数据误判成“无候选”。",
                flush=True,
            )
            return CandidateLoadResult(load_failed=True)
        except Exception as error:
            print(
                f"\033[31m[搜索候选读取失败]\033[0m chat_id={chat_id} index={index} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/候选表读取是否正常；当前相关入口会按候选读取失败或状态不可用处理，避免把持久化异常误判成“无候选”。",
                flush=True,
            )
            return CandidateLoadResult(load_failed=True)


def parse_movie_query(query: str) -> ParsedMovieQuery:
    cleaned_query = _normalize_spaces(query)
    if not cleaned_query:
        return ParsedMovieQuery(title="", year="")

    matched_parentheses = re.match(
        r"^(?P<title>.+?)\s*[\(（](?P<year>(?:19|20)\d{2})[\)）]\s*$",
        cleaned_query,
    )
    if matched_parentheses is not None:
        title = _normalize_spaces(matched_parentheses.group("title"))
        year = matched_parentheses.group("year")
        if title:
            return ParsedMovieQuery(title=title, year=year)

    matched_suffix = re.match(r"^(?P<title>.+?)\s+(?P<year>(?:19|20)\d{2})\s*$", cleaned_query)
    if matched_suffix is not None:
        title = _normalize_spaces(matched_suffix.group("title"))
        year = matched_suffix.group("year")
        if title:
            return ParsedMovieQuery(title=title, year=year)

    return ParsedMovieQuery(title=cleaned_query, year="")


def normalize_candidate(item: Mapping[str, Any]) -> Candidate:
    title = _safe_text(item.get("title"), default="(no title)")
    year = _safe_year(item.get("year"))
    quality = _safe_text(item.get("quality"), default="-")
    if quality == "-" and "resolution" in item:
        quality = _safe_text(item.get("resolution"), default="-")
    if quality == "-":
        quality = _guess_quality_from_title(title)
    size = _format_size(item.get("size"))
    indexer = _safe_indexer(item.get("indexer"), item.get("indexerName"))
    return Candidate(title=title, year=year, quality=quality, size=size, indexer=indexer)


def format_candidates(query: str, candidates: Sequence[Candidate]) -> str:
    if not candidates:
        return NO_RESULT_TEXT_TEMPLATE.format(query=query)

    lines = [f"搜索结果：{query}"]
    for i, item in enumerate(candidates, start=1):
        lines.append(f"{i}. {item.title} ({item.year})")
        lines.append(f"   画质: {item.quality} | 大小: {item.size} | 站点: {item.indexer}")
    return "\n".join(lines)


def format_movie_query_reply(
    query: str,
    parsed_query: ParsedMovieQuery,
    tmdb_movie: TmdbMovie | None,
    candidates: Sequence[Candidate],
) -> str:
    candidates_text = format_candidates(query, candidates)
    if not candidates:
        return candidates_text
    card_text = format_movie_poster_card(parsed_query, tmdb_movie)
    return f"{card_text}\n\n{candidates_text}"


def format_bt_read_only_reply(query: str, candidates: Sequence[Mapping[str, Any]]) -> str:
    if not candidates:
        return BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE.format(query=query)

    lines = [f"BT 只读探索结果：{query}"]
    for index, item in enumerate(candidates, start=1):
        title = _safe_text(item.get("title"), default="(no title)")
        indexer = _safe_indexer(item.get("indexer"), item.get("indexerName"))
        provider = _safe_text(item.get("sourceProvider"), default=indexer)
        seeders = _format_seeder_count(item.get("seeders"))
        size = _format_size(item.get("size"))
        lines.append(f"{index}. {title}")
        lines.append(f"   站点: {indexer} | 来源入口: {provider} | 做种: {seeders} | 大小: {size}")
        lines.append(f"   链接参考: {_format_bt_source_reference(item)}")
    lines.append(BT_READ_ONLY_NOTICE_TEXT)
    return "\n".join(lines)


def format_movie_poster_card(parsed_query: ParsedMovieQuery, tmdb_movie: TmdbMovie | None) -> str:
    card_title = parsed_query.title or "-"
    card_year = parsed_query.year.strip() or "-"
    card_alias = "-"

    if tmdb_movie is not None:
        original_title = _normalize_spaces(tmdb_movie.original_title)
        english_title = _normalize_spaces(tmdb_movie.title)
        if original_title:
            card_title = original_title
        elif english_title:
            card_title = english_title

        resolved_year = tmdb_movie.year.strip()
        if resolved_year:
            card_year = resolved_year

        if english_title and english_title != card_title:
            card_alias = english_title

    lines = [
        "电影海报卡片",
        f"片名: {card_title}",
        f"年份: {card_year}",
        f"别名: {card_alias}",
        "海报: 暂未接入图片",
    ]
    return "\n".join(lines)


def _safe_text(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text


def _safe_year(value: Any) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    if not text:
        return "-"
    return text


def _safe_indexer(indexer_value: Any, indexer_name_value: Any) -> str:
    if isinstance(indexer_value, Mapping):
        mapped_name = _safe_text(indexer_value.get("name"), default="-")
        if mapped_name != "-":
            return mapped_name

    name = _safe_text(indexer_name_value, default="-")
    if name != "-":
        return name
    return _safe_text(indexer_value, default="-")


def _format_seeder_count(value: Any) -> str:
    if value is None:
        return "-"
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return "-"
    if resolved < 0:
        return "-"
    return str(resolved)


def _format_bt_source_reference(item: Mapping[str, Any]) -> str:
    source = _safe_text(item.get("source"), default="-")
    if source == "-":
        return source

    info_hash = _safe_text(item.get("infoHash"), default="")
    if source.lower().startswith("magnet:?"):
        if info_hash:
            return f"magnet | infoHash={info_hash}"
        return _truncate_text(source, limit=96)

    return _truncate_text(source, limit=96)


def _format_size(size_value: Any) -> str:
    if size_value is None:
        return "-"

    try:
        bytes_value = int(size_value)
    except (TypeError, ValueError):
        return "-"

    if bytes_value <= 0:
        return "-"

    units = ("B", "KB", "MB", "GB", "TB")
    size = float(bytes_value)
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def _guess_quality_from_title(title: str) -> str:
    resolution_match = re.search(r"\b(2160p|1080p|720p|480p|4k)\b", title, flags=re.IGNORECASE)
    source_match = re.search(
        r"\b(web[- ]dl|webrip|bluray|remux|hdtv|dvdrip|bdrip)\b",
        title,
        flags=re.IGNORECASE,
    )
    if not resolution_match and not source_match:
        return "-"

    resolution = "-"
    if resolution_match:
        raw_resolution = resolution_match.group(1)
        resolution = "4K" if raw_resolution.lower() == "4k" else raw_resolution.lower()

    if not source_match:
        return resolution

    source_raw = source_match.group(1).lower().replace(" ", "-")
    source_map = {
        "web-dl": "WEB-DL",
        "webrip": "WEBRip",
        "bluray": "BluRay",
        "remux": "Remux",
        "hdtv": "HDTV",
        "dvdrip": "DVDRip",
        "bdrip": "BDRip",
    }
    source = source_map.get(source_raw, source_raw.upper())
    if resolution == "-":
        return source
    return f"{resolution} {source}"


def _to_candidate_dict(item: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in item.items()}


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _truncate_text(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return f"{value[: limit - 3]}..."


def _build_query(title: str, year: str) -> str:
    cleaned_title = _normalize_spaces(title)
    cleaned_year = year.strip()
    if not cleaned_year:
        return cleaned_title
    return f"{cleaned_title} {cleaned_year}"


async def _search_first_non_empty(search_func: SearchFunc, ordered_queries: Sequence[str]) -> Sequence[Mapping[str, Any]]:
    for query in ordered_queries:
        raw_results = await search_func(query)
        if raw_results:
            return raw_results
    return ()


async def _search_candidates_with_logging(
    *,
    search_func: SearchFunc,
    ordered_queries: Sequence[str],
    user_query: str,
) -> Sequence[Mapping[str, Any]]:
    try:
        return await _search_first_non_empty(search_func, ordered_queries)
    except Exception as error:
        query_display = " | ".join(query for query in ordered_queries if query.strip()) or user_query
        print(
            f"\033[31m[搜索源查询失败]\033[0m query={user_query} ordered_queries={query_display} 错误={error}\n\033[33m[处理建议]\033[0m 检查 Prowlarr/BT 来源、代理和网络连通性；当前搜索未拿到结果，且这不是正常的“无候选”状态。",
            flush=True,
        )
        raise


def _unique_queries(candidates: Sequence[str]) -> list[str]:
    ordered_queries: list[str] = []
    for query in candidates:
        cleaned_query = query.strip()
        if not cleaned_query:
            continue
        if cleaned_query in ordered_queries:
            continue
        ordered_queries.append(cleaned_query)
    return ordered_queries


def _format_ambiguous_clarification(
    *,
    query: str,
    parsed_query: ParsedMovieQuery,
    raw_results: Sequence[Mapping[str, Any]],
) -> str | None:
    if parsed_query.year.strip():
        return None
    if len(raw_results) < AMBIGUOUS_MIN_RESULT_COUNT:
        return None

    options = _collect_ambiguous_options(raw_results)
    if not _is_highly_ambiguous(options):
        return None

    option_lines = [f"- {option.title} ({option.year})" for option in options[:AMBIGUOUS_MAX_OPTION_COUNT]]
    if not option_lines:
        option_lines.append(AMBIGUOUS_OPTION_FALLBACK_TEXT)

    return AMBIGUOUS_QUERY_TEXT_TEMPLATE.format(
        query=query,
        options="\n".join(option_lines),
    )


def _collect_ambiguous_options(raw_results: Sequence[Mapping[str, Any]]) -> list[AmbiguousOption]:
    options: list[AmbiguousOption] = []
    seen_keys: set[tuple[str, str]] = set()
    for item in raw_results:
        title = _safe_text(item.get("title"), default="")
        if not title:
            continue
        year = _safe_year(item.get("year"))
        key = (_normalize_title_key(title), year)
        if not key[0]:
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        options.append(AmbiguousOption(title=title, year=year))
    return options


def _is_highly_ambiguous(options: Sequence[AmbiguousOption]) -> bool:
    if len(options) < 2:
        return False

    distinct_titles = {_normalize_title_key(option.title) for option in options if option.title}
    distinct_years = {option.year for option in options if option.year != "-"}
    if len(distinct_years) >= 2 and len(distinct_titles) >= 2:
        return True
    return len(options) >= 3 and len(distinct_titles) >= 3


def _normalize_title_key(title: str) -> str:
    lowered = title.lower()
    lowered = re.sub(r"\b(?:19|20)\d{2}\b", " ", lowered)
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()
