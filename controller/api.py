import hashlib
import hmac
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from controller.clients import ClusterError
from controller.runtime import ControlPlane
from controller.store import Store

WEB_DIR = Path(os.getenv("TRAFFICOPS_WEB_DIR", "/app/web"))


class Login(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class Traffic(BaseModel):
    rate: int = Field(default=10, ge=1, le=20, strict=True)
    duration: int = Field(default=180, ge=1, le=180, strict=True)
    path: Literal["/demo", "/demo/region/east", "/demo/region/west"] = "/demo"


class Weight(BaseModel):
    percent: int = Field(ge=0, le=100, strict=True)


class Errors(BaseModel):
    enabled: bool


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 310000).hex()
    return f"pbkdf2_sha256$310000${salt}${derived}"


def password_matches(password, encoded):
    try:
        encoded = encoded.strip()
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256" or int(rounds) != 310000 or len(bytes.fromhex(salt)) < 16:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_app(plane=None, store=None, admin_password_hash=None, public_origin=None, start_on_lifespan=True):
    plane = plane or ControlPlane()
    store = store or plane.store
    admin_password_hash = (admin_password_hash if admin_password_hash is not None
                           else os.getenv("TRAFFICOPS_ADMIN_PASSWORD_HASH", "")).strip()
    public_origin = public_origin or os.getenv("TRAFFICOPS_PUBLIC_ORIGIN", "")
    if not admin_password_hash or not public_origin:
        raise RuntimeError("TRAFFICOPS_ADMIN_PASSWORD_HASH and TRAFFICOPS_PUBLIC_ORIGIN must be configured")

    @asynccontextmanager
    async def lifespan(_app):
        if start_on_lifespan:
            plane.start()
        yield
        if start_on_lifespan:
            plane.stop()

    app = FastAPI(title="TrafficOps", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    def origin(request):
        if request.headers.get("origin") != public_origin:
            raise HTTPException(403, "request Origin is not allowed")

    def current_session(request):
        raw = request.cookies.get("trafficops_session", "")
        if not raw:
            raise HTTPException(401, "login required")
        session = store.session(hashlib.sha256(raw.encode()).hexdigest())
        if not session:
            raise HTTPException(401, "login required")
        csrf = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(csrf, session["csrf"]):
            raise HTTPException(403, "CSRF token is missing or invalid")
        return raw, session

    def action(call):
        try:
            return call()
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except ClusterError as exc:
            raise HTTPException(502, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/")
    def index():
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/web/{asset}")
    def asset(asset: str):
        if asset not in {"app.js", "styles.css"}:
            raise HTTPException(404)
        return FileResponse(WEB_DIR / asset)

    @app.get("/api/session")
    def session_info(request: Request):
        raw = request.cookies.get("trafficops_session", "")
        session = store.session(hashlib.sha256(raw.encode()).hexdigest()) if raw else None
        return {"authenticated": bool(session), "csrf": session["csrf"] if session else None}

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/api/login")
    def login(payload: Login, request: Request, response: Response):
        origin(request)
        if not password_matches(payload.password, admin_password_hash):
            raise HTTPException(401, "invalid password")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        store.save_session(hashlib.sha256(token.encode()).hexdigest(), csrf, time.time() + 8 * 3600)
        response.set_cookie("trafficops_session", token, httponly=True, secure=os.getenv("TRAFFICOPS_COOKIE_SECURE", "false").lower() == "true",
                            samesite="strict", max_age=8 * 3600, path="/")
        return {"authenticated": True, "csrf": csrf}

    @app.post("/api/logout")
    def logout(request: Request, response: Response):
        origin(request)
        raw, _ = current_session(request)
        store.delete_session(hashlib.sha256(raw.encode()).hexdigest())
        response.delete_cookie("trafficops_session", path="/")
        return {"authenticated": False}

    @app.get("/api/overview")
    def overview():
        return plane.overview()

    @app.get("/api/metrics")
    def metrics():
        return plane.prom.metrics()

    @app.get("/api/logs")
    def logs(marker: str = "", limit: int = 50):
        if not 1 <= limit <= 100:
            raise HTTPException(422, "limit must be between 1 and 100")
        try:
            return plane.logs(marker, limit)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/operations")
    def operations():
        return {"status": "available", "updated_at": time.time(), "operations": store.operations()}

    @app.post("/api/traffic/start")
    def traffic_start(payload: Traffic, request: Request):
        origin(request); current_session(request)
        return action(lambda: plane.start_traffic(rate=payload.rate, duration=payload.duration, path=payload.path))

    @app.post("/api/traffic/stop")
    def traffic_stop(request: Request):
        origin(request); current_session(request)
        return action(plane.stop_traffic)

    @app.post("/api/release/start")
    def release_start(request: Request):
        origin(request); current_session(request)
        return action(plane.start_release)

    @app.post("/api/release/weight")
    def release_weight(payload: Weight, request: Request):
        origin(request); current_session(request)
        return action(lambda: plane.set_weight(payload.percent))

    @app.post("/api/release/rollback")
    def release_rollback(request: Request):
        origin(request); current_session(request)
        return action(plane.rollback)

    @app.post("/api/release/complete")
    def release_complete(request: Request):
        origin(request); current_session(request)
        return action(plane.complete_release)

    @app.post("/api/incident/errors")
    def incident_errors(payload: Errors, request: Request):
        origin(request); current_session(request)
        return action(lambda: plane.set_errors(payload.enabled))

    @app.post("/api/incident/restart-pod")
    def incident_restart(request: Request):
        origin(request); current_session(request)
        return action(plane.restart_pod)

    return app


if os.getenv("TRAFFICOPS_ADMIN_PASSWORD_HASH") and os.getenv("TRAFFICOPS_PUBLIC_ORIGIN"):
    app = create_app()
else:
    @asynccontextmanager
    async def missing_configuration(_app):
        raise RuntimeError("TRAFFICOPS_ADMIN_PASSWORD_HASH and TRAFFICOPS_PUBLIC_ORIGIN must be configured")
        yield
    app = FastAPI(lifespan=missing_configuration)
