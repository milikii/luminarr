from __future__ import annotations

from collections.abc import Callable

from app.services.add_pending_context import AddPendingContextBuilder

PersistPendingAddFunc = Callable[..., str]


class AddPendingRequestFacade:
    def __init__(
        self,
        *,
        pending_context_builder: AddPendingContextBuilder,
        persist_pending_add: PersistPendingAddFunc,
        bt_source_unsupported_text: str,
    ) -> None:
        self._pending_context_builder = pending_context_builder
        self._persist_pending_add = persist_pending_add
        self._bt_source_unsupported_text = bt_source_unsupported_text

    def add_by_selection(
        self,
        *,
        chat_id: int,
        selection_text: str,
        user_id: int | None,
        channel: str | None,
        downloader_name: str,
        downloader_type: str,
        download_dir: str,
        auto_import_enabled: bool,
    ) -> str:
        build_result = self._pending_context_builder.build_from_selection(
            chat_id=chat_id,
            selection_text=selection_text,
            downloader_name=downloader_name,
            downloader_type=downloader_type,
            download_dir=download_dir,
            auto_import_enabled=auto_import_enabled,
        )
        if build_result.pending_add is None:
            return build_result.error_text
        return self._persist_pending_add(
            chat_id=chat_id,
            user_id=user_id,
            pending_add=build_result.pending_add,
            channel=channel,
        )

    def add_by_batch_selection(
        self,
        *,
        chat_id: int,
        selection_indexes: tuple[int, ...],
        user_id: int | None,
        channel: str | None,
        downloader_name: str,
        downloader_type: str,
        download_dir: str,
        auto_import_enabled: bool,
    ) -> str:
        pending_adds = []
        for index in selection_indexes:
            build_result = self._pending_context_builder.build_from_selection(
                chat_id=chat_id,
                selection_text=str(index),
                downloader_name=downloader_name,
                downloader_type=downloader_type,
                download_dir=download_dir,
                auto_import_enabled=auto_import_enabled,
            )
            if build_result.pending_add is None:
                return build_result.error_text
            pending_adds.append(build_result.pending_add)

        replies: list[str] = []
        for pending_add in pending_adds:
            replies.append(
                self._persist_pending_add(
                    chat_id=chat_id,
                    user_id=user_id,
                    pending_add=pending_add,
                    channel=channel,
                )
            )
        return "\n\n".join(replies)

    def add_candidate_source(
        self,
        *,
        chat_id: int,
        source: str,
        title: str,
        user_id: int | None,
        channel: str | None,
        downloader_name: str,
        downloader_type: str,
        download_dir: str,
        auto_import_enabled: bool,
    ) -> str:
        build_result = self._pending_context_builder.build_from_source(
            source=source,
            title=title,
            downloader_name=downloader_name,
            downloader_type=downloader_type,
            download_dir=download_dir,
            auto_import_enabled=auto_import_enabled,
        )
        if build_result.pending_add is None:
            return build_result.error_text
        return self._persist_pending_add(
            chat_id=chat_id,
            user_id=user_id,
            pending_add=build_result.pending_add,
            channel=channel,
        )

    def add_bt_source(
        self,
        *,
        chat_id: int,
        source: str,
        title: str,
        user_id: int | None,
        channel: str | None,
        downloader_name: str,
        downloader_type: str,
        download_dir: str,
        auto_import_enabled: bool,
    ) -> str:
        cleaned_source = source.strip()
        if not cleaned_source.lower().startswith("magnet:?"):
            return self._bt_source_unsupported_text
        return self.add_candidate_source(
            chat_id=chat_id,
            source=cleaned_source,
            title=title,
            user_id=user_id,
            channel=channel,
            downloader_name=downloader_name,
            downloader_type=downloader_type,
            download_dir=download_dir,
            auto_import_enabled=auto_import_enabled,
        )
