"""No page fetching, command execution, persistence of submitted text, or external inference."""
import asyncio
import hmac
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import Settings
from backend.detector import Detector
from backend.schemas import AnalyzeRequest, AnalyzeResponse


class RequestGuard:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings
        self.calls = deque()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])

        async def reject(status, code):
            await JSONResponse({"error": code}, status_code=status)(scope, receive, send)

        host = headers.get(b"host", b"").decode().lower()
        if host not in {"127.0.0.1:8765", "127.0.0.1", "localhost:8765", "localhost", "[::1]:8765", "[::1]"}:
            return await reject(400, "invalid_host")
        origin = headers.get(b"origin")
        if origin is not None and origin.decode() not in self.settings.origins:
            return await reject(403, "forbidden_origin")
        if scope["path"] != "/analyze" or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)
        if not self.settings.token:
            return await reject(503, "pairing_not_configured")
        supplied = headers.get(b"authorization", b"")
        expected = ("Bearer " + self.settings.token).encode()
        if not hmac.compare_digest(supplied, expected):
            return await reject(401, "invalid_pairing_token")
        now = time.monotonic()
        while self.calls and now - self.calls[0] >= 60:
            self.calls.popleft()
        if len(self.calls) >= 60:
            return await reject(429, "rate_limited")
        self.calls.append(now)
        body = bytearray()
        while True:
            try:
                message = await asyncio.wait_for(receive(), timeout=5)
            except TimeoutError:
                return await reject(408, "request_timeout")
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > 131072:
                return await reject(413, "request_too_large")
            if not message.get("more_body", False):
                break

        async def bounded_receive():
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, bounded_receive, send)


def create_app(settings=None):
    settings = settings or Settings.load()
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="blank-inference")

    @asynccontextmanager
    async def lifespan(app):
        yield
        executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="BLANK", version="0.3.0", docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=lifespan)
    app.state.detector = Detector(settings.model_dir)
    semaphore = asyncio.Semaphore(2)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse({"error": "invalid_request", "fields": [
            {"location": list(e["loc"]), "type": e["type"]} for e in exc.errors()
        ]}, status_code=422)

    @app.get("/health")
    def health():
        detector = app.state.detector
        return {"status": "ok", "api_version": "0.3.0", "paired": bool(settings.token),
                "ml_available": detector.pipeline is not None,
                "model_version": detector.metadata["model_version"] if detector.metadata else None,
                "reason": detector.model_reason}

    @app.post("/analyze", response_model=AnalyzeResponse, response_model_exclude_none=True)
    async def analyze(payload: AnalyzeRequest, request: Request):
        try:
            async with asyncio.timeout(4):
                async with semaphore:
                    result = await asyncio.get_running_loop().run_in_executor(
                        executor, app.state.detector.analyze, payload)
                    data = result.model_dump()
                    if data["model_scores"] is None:
                        data.pop("model_scores")
                    return JSONResponse(data)
        except TimeoutError:
            return JSONResponse({"error": "analysis_timeout"}, status_code=503)
        except Exception:
            return JSONResponse({"error": "analysis_failed"}, status_code=503)

    app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_methods=["GET", "POST"],
                       allow_headers=["Authorization", "Content-Type"])
    app.add_middleware(RequestGuard, settings=settings)
    return app


app = create_app()
