import json
from collections.abc import Awaitable, Callable
from typing import Any


class UploadTooLarge(Exception):
    pass


class UploadBodyLimitMiddleware:
    """Bound multipart request bodies before Starlette spools uploaded files."""

    def __init__(self, app: Callable[..., Awaitable[None]], max_bytes: int = 105 * 1024 * 1024) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: dict[str, Any], receive: Callable[..., Awaitable[dict[str, Any]]], send: Callable[..., Awaitable[None]]) -> None:
        path = scope.get("path", "")
        if scope.get("type") != "http" or scope.get("method") != "POST" or ("/resources" not in path):
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                await self._reject(scope, receive, send)
                return

        consumed = 0
        response_started = False

        async def limited_receive() -> dict[str, Any]:
            nonlocal consumed
            message = await receive()
            if message.get("type") == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > self.max_bytes:
                    raise UploadTooLarge
            return message

        async def tracked_send(message: dict[str, Any]) -> None:
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except UploadTooLarge:
            if not response_started:
                await self._reject(scope, receive, send)

    async def _reject(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[dict[str, Any]]],
        send: Callable[..., Awaitable[None]],
    ) -> None:
        body = json.dumps({"detail": "حجم الملف المرفوع يتجاوز الحد الأقصى المسموح به (100 ميغابايت)."}).encode("utf-8")
        headers_dict = {key.lower(): value for key, value in scope.get("headers", [])}
        origin = headers_dict.get(b"origin", b"*")
        response_headers = [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode()),
            (b"access-control-allow-origin", origin),
            (b"access-control-allow-credentials", b"true"),
            (b"access-control-allow-methods", b"GET, POST, OPTIONS, PUT, DELETE"),
            (b"access-control-allow-headers", b"*"),
        ]
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": response_headers,
            }
        )
        await send({"type": "http.response.body", "body": body})
