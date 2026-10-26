import asyncio

from app.core.middleware import UploadBodyLimitMiddleware


def test_rejects_oversized_content_length_before_app() -> None:
    sent = []
    app_called = False

    async def app(scope, receive, send):
        nonlocal app_called
        app_called = True

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        sent.append(message)

    asyncio.run(
        UploadBodyLimitMiddleware(app, max_bytes=5)(
            {"type": "http", "method": "POST", "path": "/api/v1/subjects/id/resources", "headers": [(b"content-length", b"6")]},
            receive,
            send,
        )
    )

    assert app_called is False
    assert sent[0]["status"] == 413


def test_rejects_oversized_chunked_body() -> None:
    sent = []
    messages = iter(
        [
            {"type": "http.request", "body": b"1234", "more_body": True},
            {"type": "http.request", "body": b"56", "more_body": False},
        ]
    )

    async def app(scope, receive, send):
        while True:
            message = await receive()
            if not message.get("more_body", False):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    asyncio.run(
        UploadBodyLimitMiddleware(app, max_bytes=5)(
            {"type": "http", "method": "POST", "path": "/api/v1/subjects/id/resources", "headers": []},
            receive,
            send,
        )
    )

    assert sent[0]["status"] == 413
