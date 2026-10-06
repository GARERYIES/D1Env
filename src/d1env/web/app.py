import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from ..models import DeploymentRequest, StrictModel
from ..service import ApplicationService
from .security import SecurityState


class BootstrapRequest(StrictModel):
    token: str = Field(min_length=16, max_length=256)


class StartRequest(StrictModel):
    plan_id: str = Field(min_length=1, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")


class ReportRequest(StrictModel):
    job_id: str = Field(min_length=1, max_length=128)
    mask_identifiers: bool = True


def create_app(service: ApplicationService, *, bootstrap_token: str | None = None,
               port: int = 8765) -> FastAPI:
    security = SecurityState(bootstrap_token, port)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        service.engine.reconcile_on_startup()
        yield

    app = FastAPI(title="D1Env MOCK Foundation", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.security = security
    app.state.service = service

    @app.middleware("http")
    async def boundary(request: Request, call_next: object) -> Response:
        from typing import Any, cast
        try:
            security.check_source(request)
            if request.url.path.startswith("/api/") and request.url.path != "/api/session/bootstrap":
                security.authenticate(request)
            if request.method not in {"GET", "HEAD"} and len(await request.body()) > 65536:
                raise HTTPException(413, "REQUEST_TOO_LARGE")
            response: Response = await cast(Any, call_next)(request)
        except HTTPException as exc:
            response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": e["loc"], "type": e["type"], "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse({"detail": errors}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing(request: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse({"detail": "NOT_FOUND"}, status_code=404)

    @app.exception_handler(ValueError)
    async def conflict(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.post("/api/session/bootstrap")
    def bootstrap(payload: BootstrapRequest, response: Response) -> dict[str, str]:
        session, csrf = security.bootstrap(payload.token)
        response.set_cookie("d1env_session", session, httponly=True, samesite="strict", max_age=3600)
        return {"csrf_token": csrf, "mode": "mock"}

    @app.get("/api/session")
    def session(request: Request) -> dict[str, str]:
        return {"csrf_token": security.authenticate(request), "mode": "mock"}

    @app.get("/api/catalog")
    def catalog() -> dict[str, object]:
        return service.catalog.model_dump(mode="json")

    @app.post("/api/doctor")
    def doctor(payload: DeploymentRequest) -> dict[str, object]:
        return service.doctor(payload)

    @app.post("/api/plans")
    def plans(payload: DeploymentRequest) -> dict[str, object]:
        return service.preview(payload).model_dump(mode="json")

    @app.post("/api/jobs")
    def start(payload: StartRequest) -> dict[str, object]:
        return service.start(payload.plan_id, payload.idempotency_key).model_dump(mode="json")

    @app.get("/api/jobs")
    def jobs() -> list[dict[str, object]]:
        return [job.model_dump(mode="json") for job in service.store.list_jobs()]

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str) -> dict[str, object]:
        return service.engine.get(job_id).model_dump(mode="json")

    @app.get("/api/jobs/{job_id}/events")
    def events(job_id: str, stream: bool = False) -> object:
        service.engine.get(job_id)
        if not stream:
            return [event.model_dump(mode="json") for event in service.engine.get_events(job_id)]
        async def feed() -> AsyncIterator[str]:
            seq = 0
            while True:
                for event in service.engine.get_events(job_id):
                    if event.seq > seq:
                        seq = event.seq
                        yield f"id: {seq}\ndata: {json.dumps(event.model_dump(mode='json'),ensure_ascii=False)}\n\n"
                if service.engine.get(job_id).state in {"SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED", "BLOCKED"}:
                    break
                await asyncio.sleep(.2)
        return StreamingResponse(feed(), media_type="text/event-stream")

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str) -> dict[str, object]:
        return service.engine.cancel(job_id).model_dump(mode="json")

    @app.post("/api/reports")
    def report(payload: ReportRequest) -> dict[str, object]:
        return service.report(payload.job_id, payload.mask_identifiers)

    @app.api_route("/api/{missing_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def missing_api(missing_path: str) -> Response:
        return JSONResponse({"detail": "NOT_FOUND"}, status_code=404)

    static = service.root_dir / "frontend/dist"
    if (static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/")
    def index() -> Response:
        if (static / "index.html").is_file():
            return FileResponse(static / "index.html")
        return JSONResponse({"mode": "mock", "detail": "前端尚未构建，请按开发启动方法构建"}, status_code=503)

    return app
