from __future__ import annotations

from app.services.add_pending_context import PendingAddContext
from app.services.add_to_downloader.adult import AddAdultRegistryState
from app.services.add_to_downloader.approval import PENDING_LEASE_LOOKUP_FAILED, AddConfirmApprovalState
from app.services.add_to_downloader.cancel import ADD_CANCEL_STATE_UNAVAILABLE_TEXT, ADD_CANCELLED_TEXT, AddCancelState
from app.services.add_to_downloader.execution import (
    ADD_FAILED_TEXT,
    ADD_FINALIZATION_WARNING_TEXT,
    SUPPORTED_DELIVERY_CHANNELS,
    AddConfirmFinalizationState,
    AddExecutionFollowUpService,
    AddResult,
    AddTorrentFunc,
)
from app.services.add_to_downloader.jobs import (
    DOWNLOADER_PENDING_JOB_NONE_REASON,
    DOWNLOADER_PENDING_JOB_RESULT_MISSING_REASON,
    AddConfirmContextState,
    AddConfirmJobState,
    ConfirmAvailabilityResolution,
    ConfirmExecutionContext,
    ConfirmPreparationState,
)
from app.services.add_to_downloader.rendering import (
    build_add_pending_delivery_item,
    build_duplicate_warning_delivery_item,
    render_add_pending_reply,
    render_duplicate_warning_reply,
)
from app.services.add_to_downloader.service import (
    ADD_APPROVAL_PENDING_TEXT,
    ADD_CONFIRM_EXPIRED_TEXT,
    ADD_CONFIRM_NOT_PENDING_TEXT,
    ADD_CONFIRM_STATE_UNAVAILABLE_TEXT,
    ADD_PENDING_STATE_UNAVAILABLE_TEXT,
    BT_SOURCE_UNSUPPORTED_TEXT,
    CANDIDATE_SOURCE_MISSING_TEXT,
    CONFIRM_QUERY_USAGE_TEXT,
    SELECT_LOOKUP_FAILED_TEXT,
    SELECT_NOT_FOUND_TEXT,
    SELECT_OUT_OF_RANGE_TEXT,
    SELECT_USAGE_TEXT,
    AddToDownloaderService,
)
