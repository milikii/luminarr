from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import app.bot.feishu_long_connection as feishu_long_connection_module
from app.bot.feishu_adapter import FeishuPrivateTextEvent, parse_feishu_sdk_private_text_event
from app.bot.feishu_long_connection import FeishuLongConnectionConfig, FeishuLongConnectionService


def _build_sdk_message_event(text: str) -> object:
    return SimpleNamespace(
        header=SimpleNamespace(
            event_id="feishu-sdk-event-1",
            event_type="im.message.receive_v1",
        ),
        event=SimpleNamespace(
            sender=SimpleNamespace(sender_id=SimpleNamespace(open_id="ou_feishu_user_1")),
            message=SimpleNamespace(
                message_id="om_feishu_message_1",
                chat_id="oc_feishu_chat_1",
                chat_type="p2p",
                message_type="text",
                content='{"text": "%s"}' % text,
            ),
        ),
    )


def test_parse_feishu_sdk_private_text_event_reads_private_text() -> None:
    event = parse_feishu_sdk_private_text_event(_build_sdk_message_event("cleanup"))

    assert event == FeishuPrivateTextEvent(
        event_id="feishu-sdk-event-1",
        message_id="om_feishu_message_1",
        chat_id="oc_feishu_chat_1",
        user_open_id="ou_feishu_user_1",
        text="cleanup",
    )


def test_feishu_long_connection_service_routes_sdk_event_into_shared_runtime(monkeypatch) -> None:
    route_event = AsyncMock()
    monkeypatch.setattr("app.bot.feishu_adapter.route_feishu_private_text_event", route_event)

    service = FeishuLongConnectionService(
        config=FeishuLongConnectionConfig(app_id="cli_a", app_secret="sec_b"),
        feishu_client=SimpleNamespace(),
    )
    loop = asyncio.new_event_loop()
    try:
        service._main_loop = loop
        service._bot_data = {"k": "v"}
        service._reply_text_func = AsyncMock()
        event = _build_sdk_message_event("cleanup inspect 87")

        service._handle_sdk_event(event)
        loop.run_until_complete(asyncio.sleep(0))
    finally:
        loop.close()

    route_event.assert_awaited_once()
    awaited = route_event.await_args.kwargs
    assert awaited["bot_data"] == {"k": "v"}
    assert awaited["event"].text == "cleanup inspect 87"


def test_feishu_long_connection_service_suppresses_expected_shutdown_error() -> None:
    service = FeishuLongConnectionService(
        config=FeishuLongConnectionConfig(app_id="cli_a", app_secret="sec_b"),
        feishu_client=SimpleNamespace(),
    )

    assert service._is_expected_shutdown_error(RuntimeError("Event loop stopped before Future completed."), None) is True
    assert service._is_expected_shutdown_error(RuntimeError("network down"), None) is False
    assert service._is_expected_shutdown_cancel(asyncio.CancelledError(), None) is True


def test_feishu_long_connection_service_does_not_log_start_failure_for_expected_shutdown(
    monkeypatch,
    capsys,
) -> None:
    class FakeDispatcherBuilder:
        def register_p2_im_message_receive_v1(self, handler):
            _ = handler
            return self

        def build(self) -> object:
            return object()

    class FakeEventDispatcherHandler:
        @staticmethod
        def builder(*_args: object) -> FakeDispatcherBuilder:
            return FakeDispatcherBuilder()

    class FakeWsClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def start(self) -> None:
            raise RuntimeError("Event loop stopped before Future completed.")

    monkeypatch.setattr(
        feishu_long_connection_module,
        "lark_oapi",
        SimpleNamespace(
            EventDispatcherHandler=FakeEventDispatcherHandler,
            ws=SimpleNamespace(Client=FakeWsClient),
        ),
    )
    monkeypatch.setattr(
        feishu_long_connection_module.importlib,
        "reload",
        lambda module: SimpleNamespace(Client=FakeWsClient),
    )

    service = FeishuLongConnectionService(
        config=FeishuLongConnectionConfig(app_id="cli_a", app_secret="sec_b"),
        feishu_client=SimpleNamespace(),
    )

    service._run_client_thread()

    captured = capsys.readouterr()
    assert "[Feishu 长连接启动失败]" not in captured.out


def test_feishu_long_connection_shutdown_logs_unexpected_loop_stop_request_failure(capsys) -> None:
    service = FeishuLongConnectionService(
        config=FeishuLongConnectionConfig(app_id="cli_a", app_secret="sec_b"),
        feishu_client=SimpleNamespace(),
    )
    service._thread_loop = SimpleNamespace(
        is_closed=lambda: False,
        stop=lambda: None,
        call_soon_threadsafe=lambda callback: (_ for _ in ()).throw(RuntimeError("network down")),
    )
    service._ws_client = SimpleNamespace()
    service._thread = SimpleNamespace(join=lambda timeout=0: None)

    asyncio.run(service.shutdown())

    captured = capsys.readouterr()
    assert "[Feishu 长连接关闭失败]" in captured.out
    assert "network down" in captured.out
    assert "[处理建议]" in captured.out


def test_feishu_long_connection_shutdown_suppresses_expected_loop_stop_request_error(capsys) -> None:
    service = FeishuLongConnectionService(
        config=FeishuLongConnectionConfig(app_id="cli_a", app_secret="sec_b"),
        feishu_client=SimpleNamespace(),
    )
    service._thread_loop = SimpleNamespace(
        is_closed=lambda: False,
        stop=lambda: None,
        call_soon_threadsafe=lambda callback: (_ for _ in ()).throw(RuntimeError("Event loop is closed")),
    )
    service._ws_client = SimpleNamespace()
    service._thread = SimpleNamespace(join=lambda timeout=0: None)

    asyncio.run(service.shutdown())

    captured = capsys.readouterr()
    assert "[Feishu 长连接关闭失败]" not in captured.out


def test_feishu_long_connection_logs_unexpected_loop_stop_failure(
    monkeypatch,
    capsys,
) -> None:
    class FakeDispatcherBuilder:
        def register_p2_im_message_receive_v1(self, handler):
            _ = handler
            return self

        def build(self) -> object:
            return object()

    class FakeEventDispatcherHandler:
        @staticmethod
        def builder(*_args: object) -> FakeDispatcherBuilder:
            return FakeDispatcherBuilder()

    class FakeWsClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def start(self) -> None:
            return None

    fake_loop = SimpleNamespace(
        set_exception_handler=lambda handler: None,
        stop=lambda: (_ for _ in ()).throw(RuntimeError("loop stop failed")),
        close=lambda: None,
    )

    monkeypatch.setattr(
        feishu_long_connection_module,
        "lark_oapi",
        SimpleNamespace(
            EventDispatcherHandler=FakeEventDispatcherHandler,
            ws=SimpleNamespace(Client=FakeWsClient),
        ),
    )
    monkeypatch.setattr(
        feishu_long_connection_module.importlib,
        "reload",
        lambda module: SimpleNamespace(Client=FakeWsClient),
    )
    monkeypatch.setattr(feishu_long_connection_module.asyncio, "new_event_loop", lambda: fake_loop)
    monkeypatch.setattr(feishu_long_connection_module.asyncio, "set_event_loop", lambda loop: None)

    service = FeishuLongConnectionService(
        config=FeishuLongConnectionConfig(app_id="cli_a", app_secret="sec_b"),
        feishu_client=SimpleNamespace(),
    )

    service._run_client_thread()

    captured = capsys.readouterr()
    assert "[Feishu 长连接停止失败]" in captured.out
    assert "loop stop failed" in captured.out
    assert "[处理建议]" in captured.out


def test_feishu_long_connection_suppresses_expected_loop_stop_error(
    monkeypatch,
    capsys,
) -> None:
    class FakeDispatcherBuilder:
        def register_p2_im_message_receive_v1(self, handler):
            _ = handler
            return self

        def build(self) -> object:
            return object()

    class FakeEventDispatcherHandler:
        @staticmethod
        def builder(*_args: object) -> FakeDispatcherBuilder:
            return FakeDispatcherBuilder()

    class FakeWsClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def start(self) -> None:
            return None

    fake_loop = SimpleNamespace(
        set_exception_handler=lambda handler: None,
        stop=lambda: (_ for _ in ()).throw(RuntimeError("Event loop is closed")),
        close=lambda: None,
    )

    monkeypatch.setattr(
        feishu_long_connection_module,
        "lark_oapi",
        SimpleNamespace(
            EventDispatcherHandler=FakeEventDispatcherHandler,
            ws=SimpleNamespace(Client=FakeWsClient),
        ),
    )
    monkeypatch.setattr(
        feishu_long_connection_module.importlib,
        "reload",
        lambda module: SimpleNamespace(Client=FakeWsClient),
    )
    monkeypatch.setattr(feishu_long_connection_module.asyncio, "new_event_loop", lambda: fake_loop)
    monkeypatch.setattr(feishu_long_connection_module.asyncio, "set_event_loop", lambda loop: None)

    service = FeishuLongConnectionService(
        config=FeishuLongConnectionConfig(app_id="cli_a", app_secret="sec_b"),
        feishu_client=SimpleNamespace(),
    )

    service._run_client_thread()

    captured = capsys.readouterr()
    assert "[Feishu 长连接停止失败]" not in captured.out
