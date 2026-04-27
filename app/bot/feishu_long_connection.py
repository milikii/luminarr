from __future__ import annotations

import asyncio
import importlib
import threading
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.clients.feishu import FeishuClient
from app.operational_logging import emit_operational_log

if TYPE_CHECKING:
    from app.bot.feishu_adapter import FeishuPrivateTextEvent

FEISHU_LONG_CONNECTION_SERVICE_KEY = "feishu_long_connection_service"

try:
    import lark_oapi
    import lark_oapi.ws.client as lark_ws_client_module
except ImportError as import_error:  # pragma: no cover - exercised via availability checks
    lark_oapi = None
    lark_ws_client_module = None
    _FEISHU_LONG_CONNECTION_IMPORT_ERROR = import_error
else:
    _FEISHU_LONG_CONNECTION_IMPORT_ERROR = None


@dataclass(frozen=True, slots=True)
class FeishuLongConnectionConfig:
    app_id: str
    app_secret: str


class FeishuLongConnectionService:
    def __init__(
        self,
        *,
        config: FeishuLongConnectionConfig,
        feishu_client: FeishuClient,
    ) -> None:
        self._config = config
        self._feishu_client = feishu_client
        self._thread: threading.Thread | None = None
        self._thread_loop: asyncio.AbstractEventLoop | None = None
        self._ws_client: Any = None
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._bot_data: MutableMapping[str, object] | None = None
        self._reply_text_func: Callable[["FeishuPrivateTextEvent", str], Awaitable[object]] | None = None

    def is_available(self) -> bool:
        return lark_oapi is not None and lark_ws_client_module is not None

    async def start(self, *, bot_data: MutableMapping[str, object]) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        if not self.is_available():
            reason = _FEISHU_LONG_CONNECTION_IMPORT_ERROR or "lark-oapi dependency is missing"
            emit_operational_log(
                title="Feishu 长连接未就绪",
                detail=f"原因={reason}",
                fix_hint="安装 lark-oapi，并确认当前环境可访问 Feishu 长连接服务。",
            )
            return

        self._main_loop = asyncio.get_running_loop()
        self._bot_data = bot_data
        from app.bot.feishu_adapter import build_feishu_reply_text_func

        self._reply_text_func = build_feishu_reply_text_func(self._feishu_client)
        thread = threading.Thread(
            target=self._run_client_thread,
            name="feishu-long-connection",
            daemon=True,
        )
        thread.start()
        self._thread = thread
        emit_operational_log(
            title="Feishu 长连接已启动",
            detail="当前入站将通过官方 SDK 长连接接收事件。",
            fix_hint="Feishu 长连接正在接收事件。",
        )

    async def shutdown(self) -> None:
        loop = self._thread_loop
        thread = self._thread
        self._thread = None
        self._ws_client = None
        self._thread_loop = None
        if loop is None or thread is None:
            return
        self._request_thread_loop_stop(loop)
        thread.join(timeout=5.0)

    @staticmethod
    def _is_expected_shutdown_error(error: Exception, thread: threading.Thread | None) -> bool:
        return thread is None and "Event loop stopped before Future completed" in str(error)

    @staticmethod
    def _is_expected_shutdown_cancel(error: BaseException, thread: threading.Thread | None) -> bool:
        return thread is None and isinstance(error, asyncio.CancelledError)

    @staticmethod
    def _is_expected_loop_stop_error(error: Exception) -> bool:
        error_text = str(error)
        return "Event loop is closed" in error_text or "Event loop stopped before Future completed" in error_text

    def _request_thread_loop_stop(self, loop: asyncio.AbstractEventLoop) -> None:
        if loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception as error:
            if not self._is_expected_loop_stop_error(error):
                emit_operational_log(
                    title="Feishu 长连接关闭失败",
                    detail=f"原因={error}",
                    fix_hint="检查 Feishu 线程事件循环是否仍可停止；如服务仍在运行，可稍后重试停机或检查上游 SDK 状态。",
                )

    @staticmethod
    def _reload_ws_client_module() -> Any:
        assert lark_ws_client_module is not None
        return importlib.reload(lark_ws_client_module)

    def _handle_loop_exception(self, loop: asyncio.AbstractEventLoop, context: dict[str, object]) -> None:
        exception = context.get("exception")
        if self._thread is None and context.get("message") == "Task exception was never retrieved":
            if exception is not None and exception.__class__.__name__ == "ConnectionClosedOK":
                return
        loop.default_exception_handler(context)

    def _run_client_thread(self) -> None:
        assert lark_oapi is not None
        assert lark_ws_client_module is not None
        thread_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(thread_loop)
        thread_loop.set_exception_handler(self._handle_loop_exception)
        self._thread_loop = thread_loop
        try:
            ws_client_module = self._reload_ws_client_module()
            event_handler = (
                lark_oapi.EventDispatcherHandler.builder("", "")
                .register_p2_im_message_receive_v1(self._handle_sdk_event)
                .build()
            )
            client = ws_client_module.Client(
                self._config.app_id,
                self._config.app_secret,
                event_handler=event_handler,
            )
            self._ws_client = client
            client.start()
        except BaseException as error:
            if self._is_expected_shutdown_error(error, self._thread):
                return
            if self._is_expected_shutdown_cancel(error, self._thread):
                return
            if not isinstance(error, Exception):
                raise
            emit_operational_log(
                title="Feishu 长连接启动失败",
                detail=f"原因={error}",
                fix_hint="检查 FEISHU_APP_ID/FEISHU_APP_SECRET，以及当前网络是否可访问 Feishu 长连接服务。",
            )
        finally:
            try:
                thread_loop.stop()
            except Exception as error:
                if not self._is_expected_loop_stop_error(error):
                    emit_operational_log(
                        title="Feishu 长连接停止失败",
                        detail=f"原因={error}",
                        fix_hint="检查 Feishu 线程事件循环是否仍可停止；如当前进程还在运行，可稍后重试停机或检查上游 SDK 状态。",
                    )
            thread_loop.close()

    def _handle_sdk_event(self, payload: object) -> None:
        if self._main_loop is None or self._bot_data is None or self._reply_text_func is None:
            return
        from app.bot.feishu_adapter import (
            parse_feishu_sdk_private_text_event,
            route_feishu_private_text_event,
        )

        event = parse_feishu_sdk_private_text_event(payload)
        if event is None:
            return
        future = asyncio.run_coroutine_threadsafe(
            route_feishu_private_text_event(
                event=event,
                bot_data=self._bot_data,
                reply_text_func=self._reply_text_func,
            ),
            self._main_loop,
        )
        future.add_done_callback(self._log_future_error)

    @staticmethod
    def _log_future_error(future: Any) -> None:
        try:
            future.result()
        except Exception as error:
            emit_operational_log(
                title="Feishu 长连接事件处理失败",
                detail=f"原因={error}",
                fix_hint="检查 Feishu 事件内容、shared private-chat runtime 依赖和回复链路。",
            )
