from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import MutableMapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True, slots=True)
class WeComWebhookServerConfig:
    host: str
    port: int
    path: str


@dataclass(frozen=True, slots=True)
class WeComWebhookServerRuntime:
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


def start_wecom_webhook_server(
    *,
    loop: asyncio.AbstractEventLoop,
    config: WeComWebhookServerConfig,
    bot_data: MutableMapping[str, object],
) -> WeComWebhookServerRuntime:
    handler_class = _build_handler_class(
        loop=loop,
        path=config.path,
        bot_data=bot_data,
    )
    server = HTTPServer((config.host, config.port), handler_class)
    thread = threading.Thread(target=server.serve_forever, name="wecom-webhook-server", daemon=True)
    thread.start()
    print(f"\033[32m[WeCom webhook 已启动]\033[0m 地址=http://{config.host}:{server.server_address[1]}{config.path}")
    return WeComWebhookServerRuntime(server=server, thread=thread, path=config.path)


def stop_wecom_webhook_server(runtime: WeComWebhookServerRuntime) -> None:
    runtime.server.shutdown()
    runtime.server.server_close()
    runtime.thread.join(timeout=5.0)


def _build_handler_class(
    *,
    loop: asyncio.AbstractEventLoop,
    path: str,
    bot_data: MutableMapping[str, object],
) -> type[BaseHTTPRequestHandler]:
    class WeComWebhookHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self._handle_request(method="GET")

        def do_POST(self) -> None:  # noqa: N802
            self._handle_request(method="POST")

        def log_message(self, format: str, *args: object) -> None:
            return

        def _handle_request(self, *, method: str) -> None:
            from app.bot.wecom_adapter import handle_wecom_callback_http_request

            parsed_url = urlparse(self.path)
            if parsed_url.path != path:
                self._write_response(
                    _HttpResponse(
                        status_code=404,
                        body=json.dumps({"code": 404, "msg": "not found"}).encode("utf-8"),
                    )
                )
                return

            body = b""
            if method == "POST":
                content_length = _parse_content_length(self.headers.get("Content-Length"))
                body = self.rfile.read(content_length)

            future = asyncio.run_coroutine_threadsafe(
                handle_wecom_callback_http_request(
                    method=method,
                    query_params=parse_qs(parsed_url.query, keep_blank_values=True),
                    body=body,
                    bot_data=bot_data,
                ),
                loop,
            )
            try:
                response = future.result(timeout=30.0)
            except Exception as error:
                print(
                    f"\033[31m[WeCom webhook HTTP 入口失败]\033[0m 原因={error}\n"
                    "\033[33m[处理建议]\033[0m 检查事件循环是否仍在运行，以及 WeCom webhook 路径配置是否正确。"
                )
                response = _HttpResponse(
                    status_code=500,
                    body=json.dumps({"code": 500, "msg": "internal error"}).encode("utf-8"),
                )
            self._write_response(response)

        def _write_response(self, response: _HttpResponse | object) -> None:
            try:
                status_code = int(getattr(response, "status_code"))
                body = bytes(getattr(response, "body"))
                content_type = str(getattr(response, "content_type", "application/octet-stream"))
                self.send_response(status_code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)
            except OSError as error:
                print(
                    f"\033[31m[WeCom webhook 回包失败]\033[0m 路径={self.path} 原因={error}\n"
                    "\033[33m[处理建议]\033[0m 检查回调对端是否提前断开连接，并确认当前 WeCom 回包链仍可写 socket。",
                    flush=True,
                )

    return WeComWebhookHandler


def _parse_content_length(raw_value: str | None) -> int:
    if raw_value is None:
        return 0
    try:
        return max(int(raw_value), 0)
    except ValueError:
        return 0
