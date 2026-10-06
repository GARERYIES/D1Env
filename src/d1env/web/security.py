import hmac
import secrets
import threading
import time

from fastapi import HTTPException, Request


class SecurityState:
    def __init__(self, bootstrap_token: str | None = None, port: int = 8765) -> None:
        self.bootstrap_token: str | None = bootstrap_token or secrets.token_urlsafe(32)
        self.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        self.sessions: dict[str, tuple[str, float]] = {}
        self.lock = threading.Lock()

    def check_source(self, request: Request) -> None:
        host = request.headers.get("host", "")
        if host not in self.allowed_hosts or request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403, "HOST_OR_SOURCE_REJECTED")
        origin = request.headers.get("origin")
        if origin is not None and origin != f"http://{host}":
            raise HTTPException(403, "ORIGIN_REJECTED")
        if request.method not in {"GET", "HEAD"} and origin != f"http://{host}":
            raise HTTPException(403, "SAME_ORIGIN_REQUIRED")

    def bootstrap(self, token: str) -> tuple[str, str]:
        with self.lock:
            if self.bootstrap_token is None or not hmac.compare_digest(token.encode(), self.bootstrap_token.encode()):
                raise HTTPException(401, "BOOTSTRAP_INVALID_OR_USED")
            self.bootstrap_token = None
            session, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            self.sessions[session] = (csrf, time.monotonic() + 3600)
            return session, csrf

    def authenticate(self, request: Request) -> str:
        session = request.cookies.get("d1env_session", "")
        with self.lock:
            record = self.sessions.get(session)
        if record is None or record[1] < time.monotonic():
            raise HTTPException(401, "SESSION_REQUIRED")
        if request.method not in {"GET", "HEAD"} and not hmac.compare_digest(request.headers.get("x-csrf-token", "").encode(), record[0].encode()):
            raise HTTPException(403, "CSRF_REJECTED")
        return record[0]
