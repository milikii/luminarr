from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx


RPC_URL = "http://127.0.0.1:19092/transmission/rpc"
OUTPUT_PATH = Path("/tmp/luminarr_bt_transmission_rpc_probe.json")
ATTEMPTS = 5
TIMEOUT_SECONDS = 3.0


async def main() -> int:
    attempts: list[dict[str, object]] = []
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
        for _ in range(ATTEMPTS):
            started_at = datetime.now(UTC).isoformat()
            try:
                response = await client.post(RPC_URL, json={"method": "session-get"})
            except Exception as error:
                attempts.append(
                    {
                        "time": started_at,
                        "ok": False,
                        "error": str(error),
                    }
                )
                continue
            attempts.append(
                {
                    "time": started_at,
                    "ok": response.status_code in {200, 409},
                    "status_code": response.status_code,
                    "session_id": response.headers.get("X-Transmission-Session-Id", ""),
                    "body_head": response.text[:200],
                }
            )

    summary = {
        "rpc_url": RPC_URL,
        "attempts": attempts,
        "success_count": sum(1 for item in attempts if bool(item.get("ok"))),
    }
    OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
