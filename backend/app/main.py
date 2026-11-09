"""AFED API entry point."""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import CORS_ORIGINS, MAX_BODY_BYTES, MAX_UPLOAD_BYTES
from .db import SessionLocal, init_db
from .routers import alerts, auth, cases, dashboard, entities, evaluation, notifications, reports, settings, upload, users
from .services import mark_interrupted_runs


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    with SessionLocal() as db:
        mark_interrupted_runs(db)
    yield


app = FastAPI(title="AFED API", version="1.0.0", lifespan=lifespan,
              description="Automated Fraud and Event Detection")


class RequestGuard:
    """Turn away oversized or malformed requests before anything reads them, and before any auth check.

    Without a length up front a body could not be sized without reading it, so those are refused too.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            refusal = self._refusal(scope)
            if refusal:
                await JSONResponse({"detail": refusal[1]}, status_code=refusal[0])(scope, receive, send)
                return
        await self.app(scope, receive, send)

    @staticmethod
    def _refusal(scope: dict[str, Any]) -> tuple[int, str] | None:
        if b"%00" in scope.get("query_string", b"") or "\x00" in scope["path"]:
            return 400, "Invalid request"
        headers = dict(scope["headers"])
        limit = MAX_UPLOAD_BYTES + 65536 if scope["path"].endswith(("/upload/preview", "/upload/events")) else MAX_BODY_BYTES
        length = headers.get(b"content-length")
        if length is None and b"transfer-encoding" in headers:
            return 411, "A content length is required"
        if length is not None and (not length.isdigit() or int(length) > limit):
            return 413, "The request is too large"
        return None


app.add_middleware(RequestGuard)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
    # Replaces the default handler, which echoes the input and fails on values JSON cannot hold, such as NaN.
    return JSONResponse(status_code=422, content={"detail": [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in error.errors()]})


for module in (auth, dashboard, alerts, cases, entities, upload, settings, evaluation, reports, notifications, users):
    app.include_router(module.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
