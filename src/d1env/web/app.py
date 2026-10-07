import asyncio
import json
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from ..models import DeploymentRequest, JSONValue, StrictModel
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


class PrepareRuntimeRequest(StrictModel):
    request_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]+$")


class EmptyRequest(StrictModel):
    pass


class ContinueRuntimeRequest(StrictModel):
    action: str = Field(pattern=r"^(accept_license|check_again)$")


def create_app(service: ApplicationService, *, bootstrap_token: str | None = None,
               port: int = 8765) -> FastAPI:
    security = SecurityState(bootstrap_token, port)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        service.engine.reconcile_on_startup()
        # Initialize/recover private setup state at startup; later GETs stay read-only.
        _ = service.runtime_setup
        yield

    app = FastAPI(title="D1Env 本地部署", docs_url=None, redoc_url=None,
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
            if request.method not in {"GET", "HEAD"} and request.url.path != "/api/artifacts/ros-probe/import":
                parts: list[bytes] = []
                size = 0
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > 65536:
                        raise HTTPException(413, "REQUEST_TOO_LARGE")
                    parts.append(chunk)
                # Starlette CachedRequest replays this bounded body to call_next.
                request._body = b"".join(parts)
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
        prefix = str(exc).partition(":")[0]
        code = getattr(exc, "code", prefix)
        if not isinstance(code, str) or re.fullmatch(r"[A-Z][A-Z0-9_]{0,80}", code) is None:
            code = "VALIDATION_BLOCKED"
        return JSONResponse({"detail": {"code": code, "message": str(exc)[:2048],
            "remediation": "按失败证据核对配置、完整发行工件和 Docker 状态，再重试；不会自动放宽权限。"}}, status_code=409)

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
        return [service.engine.get(job.job_id).model_dump(mode="json") for job in service.store.list_jobs()]

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str) -> dict[str, object]:
        return service.engine.get(job_id).model_dump(mode="json")

    @app.get("/api/jobs/{job_id}/plan")
    def job_plan(job_id: str) -> dict[str, object]:
        saved = service.store.get_job(job_id)
        return service.store.get_plan(saved.plan_id).model_dump(mode="json")

    @app.get("/api/jobs/{job_id}/events")
    def events(job_id: str, stream: bool = False) -> object:
        service.store.get_job(job_id)
        if not stream:
            return [event.model_dump(mode="json") for event in service.engine.get_events(job_id)]
        async def feed() -> AsyncIterator[str]:
            seq = 0
            while True:
                for event in service.engine.get_events(job_id):
                    if event.seq > seq:
                        seq = event.seq
                        yield f"id: {seq}\ndata: {json.dumps(event.model_dump(mode='json'),ensure_ascii=False)}\n\n"
                if service.store.get_job(job_id).state in {"SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED", "BLOCKED"}:
                    break
                await asyncio.sleep(.2)
        return StreamingResponse(feed(), media_type="text/event-stream")

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str) -> dict[str, object]:
        return service.engine.cancel(job_id).model_dump(mode="json")

    @app.post("/api/jobs/{job_id}/stop")
    def stop(job_id: str) -> dict[str, object]:
        return service.stop(job_id).model_dump(mode="json")

    @app.post("/api/reports")
    def report(payload: ReportRequest) -> dict[str, object]:
        return service.report(payload.job_id, payload.mask_identifiers)

    @app.get("/api/runtime/status")
    def runtime_status() -> dict[str, JSONValue]:
        return service.runtime_setup.status()

    @app.post("/api/runtime/prepare")
    def runtime_prepare(payload: PrepareRuntimeRequest) -> dict[str, JSONValue]:
        return service.runtime_setup.prepare(payload.request_key)

    def runtime_id(task_id: str) -> str:
        if re.fullmatch(r"[0-9a-f]{32}", task_id) is None:
            raise HTTPException(422, "RUNTIME_TASK_ID_INVALID")
        return task_id

    @app.get("/api/runtime/tasks/{task_id}")
    def runtime_task(task_id: str) -> dict[str, JSONValue]:
        return service.runtime_setup.get(runtime_id(task_id))

    @app.post("/api/runtime/tasks/{task_id}/continue")
    def runtime_continue(task_id: str, payload: ContinueRuntimeRequest) -> dict[str, JSONValue]:
        return service.runtime_setup.continue_task(runtime_id(task_id), payload.action)

    @app.post("/api/runtime/tasks/{task_id}/cancel")
    def runtime_cancel(task_id: str, payload: EmptyRequest) -> dict[str, JSONValue]:
        return service.runtime_setup.cancel(runtime_id(task_id))

    @app.get("/api/artifacts/ros-probe")
    def ros_artifact() -> dict[str, JSONValue]:
        return service.ros_image_metadata()

    @app.post("/api/artifacts/ros-probe/import")
    async def import_ros_artifact(request: Request) -> dict[str, JSONValue]:
        metadata = service.ros_image_metadata()["trusted_bundle"]
        if not isinstance(metadata, dict):
            raise HTTPException(409, "OFFLINE_IMPORT_BLOCKED: 缺少可信发行工件；导入已禁用。")
        maximum = metadata.get("size_bytes")
        if not isinstance(maximum, int):
            raise HTTPException(409, "OFFLINE_IMPORT_BLOCKED: 工件大小未知；请使用完整发行包。")
        if request.headers.get("Content-Type", "").split(";")[0] != "application/octet-stream":
            raise HTTPException(415, "IMPORT_CONTENT_TYPE: 请选择发行包提供的镜像文件。")
        content_length = request.headers.get("Content-Length")
        if content_length is not None and (not content_length.isdecimal() or int(content_length) != maximum):
            raise HTTPException(413, "IMPORT_SIZE_MISMATCH: 文件大小与发行记录不符。")
        uploads = service.store.path.parent / "uploads"
        uploads.mkdir(exist_ok=True, mode=0o700)
        if uploads.is_symlink() or uploads.stat().st_mode & 0o022:
            raise HTTPException(409, "UPLOAD_DIRECTORY_UNSAFE: 请检查用户状态目录权限。")
        path = uploads / f"{uuid4().hex}.bundle"
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            size = 0
            with os.fdopen(descriptor, "wb") as output:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > maximum:
                        raise HTTPException(413, "IMPORT_SIZE_MISMATCH: 工件超过可信发行大小。")
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if size != maximum:
                raise HTTPException(409, "IMPORT_INCOMPLETE: 上传中断或大小不符；请重新选择完整文件。")
            return await run_in_threadpool(service.import_ros_image, path)
        finally:
            path.unlink(missing_ok=True)

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
