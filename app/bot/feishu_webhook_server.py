from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class FeishuWebhookServerConfig:
    host: str
    port: int
    path: str


@dataclass(frozen=True, slots=True)
class FeishuWebhookServerRuntime:
    server: HTTPServer
    thread: threading.Thread
    path: str

    @property
    def port(self) -> int:
        return int(self.server.server_address[1])


@dataclass(frozen=True, slots=True)
class _HttpResponse:
    status_code: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"


def start_feishu_webhook_server(
    *,
    loop: asyncio.AbstractEventLoop,
    config: FeishuWebhookServerConfig,
    bot_data: MutableMapping[str, object],
    reply_text_func: Callable[[Any, str], Awaitable[object]],
) -> FeishuWebhookServerRuntime:
    handler_class = _build_handler_class(
        loop=loop,
        path=config.path,
        bot_data=bot_data,
        reply_text_func=reply_text_func,
    )
    server = HTTPServer((config.host, config.port), handler_class)
    thread = threading.Thread(target=server.serve_forever, name="feishu-webhook-server", daemon=True)
    thread.start()
    print(
        f"\033[32m[Feishu webhook 已启动]\033[0m 地址=http://{config.host}:{server.server_address[1]}{config.path}"
    )
    return FeishuWebhookServerRuntime(server=server, thread=thread, path=config.path)


def stop_feishu_webhook_server(runtime: FeishuWebhookServerRuntime) -> None:
    runtime.server.shutdown()
    runtime.server.server_close()
    runtime.thread.join(timeout=5.0)


def _build_handler_class(
    *,
    loop: asyncio.AbstractEventLoop,
    path: str,
    bot_data: MutableMapping[str, object],
    reply_text_func: Callable[[Any, str], Awaitable[object]],
) -> type[BaseHTTPRequestHandler]:
    class FeishuWebhookHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            from app.bot.feishu_adapter import handle_feishu_webhook_http_request

            request_path = urlparse(self.path).path
            if request_path != path:
                self._write_json_response(
                    _HttpResponse(
                        status_code=404,
                        body=json.dumps({"code": 404, "msg": "not found"}).encode("utf-8"),
                    )
                )
                return

            content_length = _parse_content_length(self.headers.get("Content-Length"))
            request_body = self.rfile.read(content_length)
            future = asyncio.run_coroutine_threadsafe(
                handle_feishu_webhook_http_request(
                    body=request_body,
                    headers=dict(self.headers.items()),
                    bot_data=bot_data,
                    reply_text_func=reply_text_func,
                ),
                loop,
            )
            try:
                response = future.result(timeout=30.0)
            except Exception as error:
                print(
                    f"\033[31m[Feishu webhook HTTP 入口失败]\033[0m 原因={error}\n"
                    "\033[33m[处理建议]\033[0m 检查事件循环是否仍在运行，以及 Feishu webhook 路径配置是否正确。"
                )
                response = _HttpResponse(
                    status_code=500,
                    body=json.dumps({"code": 500, "msg": "internal error"}).encode("utf-8"),
                )
            self._write_json_response(response)

        def do_GET(self) -> None:  # noqa: N802
            self._write_json_response(
                _HttpResponse(
                    status_code=405,
                    body=json.dumps({"code": 405, "msg": "method not allowed"}).encode("utf-8"),
                )
            )

        def log_message(self, format: str, *args: object) -> None:
            return

        def _write_json_response(self, response: Any) -> None:
            try:
                self.send_response(response.status_code)
                self.send_header("Content-Type", response.content_type)
                self.send_header("Content-Length", str(len(response.body)))
                self.end_headers()
                if response.body:
                    self.wfile.write(response.body)
            except OSError as error:
                print(
                    f"\033[31m[Feishu webhook 回包失败]\033[0m 路径={self.path} 原因={error}\n"
                    "\033[33m[处理建议]\033[0m 检查回调对端是否提前断开连接，并确认当前 webhook 回包链仍可写 socket。",
                    flush=True,
                )

    return FeishuWebhookHandler


def _parse_content_length(raw_value: str | None) -> int:
    if raw_value is None:
        return 0
    try:
        return max(int(raw_value), 0)
    except ValueError:
        return 0
