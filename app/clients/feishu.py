from __future__ import annotations

import json
import time

import httpx


class FeishuClientError(RuntimeError):
    """Raised when Feishu API calls fail."""


class FeishuClient:
    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        base_url: str = "https://open.feishu.cn",
        timeout_seconds: float = 10.0,
    ) -> None:
        self._app_id = app_id.strip()
        self._app_secret = app_secret.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._tenant_access_token = ""
        self._tenant_access_token_expires_at = 0.0

    async def send_private_text(self, *, chat_id: str, text: str) -> str:
        tenant_access_token = await self._get_tenant_access_token()
        payload = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }
        headers = {
            "Authorization": f"Bearer {tenant_access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(
                f"{self._base_url}/open-apis/im/v1/messages",
                params={"receive_id_type": "chat_id"},
                headers=headers,
                json=payload,
            )
        response_payload = self._decode_json_response(
            response=response,
            error_title="Feishu 文本回消息失败",
            fix_hint="检查 FEISHU_APP_ID、FEISHU_APP_SECRET、FEISHU_BASE_URL，以及机器人消息权限和 chat_id 是否有效。",
        )
        response_code = int(response_payload.get("code", -1))
        if response.status_code >= 400 or response_code != 0:
            self._log_api_error(
                title="Feishu 文本回消息失败",
                detail=(
                    f"状态={response.status_code} code={response_payload.get('code', '-')}"
                    f" msg={response_payload.get('msg', '-')}"
                ),
                fix_hint="检查 FEISHU_APP_ID、FEISHU_APP_SECRET、FEISHU_BASE_URL，以及机器人消息权限和 chat_id 是否有效。",
            )
            raise FeishuClientError("feishu send private text failed")

        data = response_payload.get("data")
        if not isinstance(data, dict):
            return ""
        return str(data.get("message_id", "")).strip()

    async def _get_tenant_access_token(self) -> str:
        now = time.monotonic()
        if self._tenant_access_token and now < self._tenant_access_token_expires_at:
            return self._tenant_access_token

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(
                f"{self._base_url}/open-apis/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self._app_id,
                    "app_secret": self._app_secret,
                },
            )
        payload = self._decode_json_response(
            response=response,
            error_title="Feishu access token 获取失败",
            fix_hint="检查 FEISHU_APP_ID、FEISHU_APP_SECRET、FEISHU_BASE_URL，以及当前网络是否可访问 Feishu OpenAPI。",
        )
        response_code = int(payload.get("code", -1))
        tenant_access_token = str(payload.get("tenant_access_token", "")).strip()
        expire_seconds = int(payload.get("expire", 0) or 0)
        if response.status_code >= 400 or response_code != 0 or not tenant_access_token:
            self._log_api_error(
                title="Feishu access token 获取失败",
                detail=(
                    f"状态={response.status_code} code={payload.get('code', '-')}"
                    f" msg={payload.get('msg', '-')}"
                ),
                fix_hint="检查 FEISHU_APP_ID、FEISHU_APP_SECRET、FEISHU_BASE_URL，以及当前网络是否可访问 Feishu OpenAPI。",
            )
            raise FeishuClientError("feishu tenant access token failed")

        self._tenant_access_token = tenant_access_token
        self._tenant_access_token_expires_at = now + max(expire_seconds - 60, 0)
        return tenant_access_token

    def _decode_json_response(
        self,
        *,
        response: httpx.Response,
        error_title: str,
        fix_hint: str,
    ) -> dict[str, object]:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            self._log_api_error(
                title=error_title,
                detail=f"状态={response.status_code} 返回体不是合法 JSON：{response.text[:200]}",
                fix_hint=fix_hint,
            )
            raise FeishuClientError(f"{error_title}: invalid json response") from None
        if not isinstance(payload, dict):
            self._log_api_error(
                title=error_title,
                detail=f"状态={response.status_code} 返回体不是对象：{payload!r}",
                fix_hint=fix_hint,
            )
            raise FeishuClientError(f"{error_title}: invalid json payload")
        return payload

    def _log_api_error(self, *, title: str, detail: str, fix_hint: str) -> None:
        print(f"\033[31m[{title}]\033[0m {detail}\n\033[33m[处理建议]\033[0m {fix_hint}")
