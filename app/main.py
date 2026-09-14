"""独立 FastAPI 应用；仅在生命周期启动时加载本项目数据。"""

import asyncio
import hmac
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.community import router
from app.core import kuro_login, miyoushe_missions
from app.core.community_scheduler import CommunityActivityInProgressError
from app.core.runtime import runtime
from app.core.state import state
from app.models.schema import SessionLoginIn, SessionOut
from app.services.access import RemoteAccess, RemoteSessions
from app.services.diagnostics import Diagnostics
from app.tools.community_contract import CommunitySignInProgressError
from app.utils.logger import configure_file_logging, get_logger
from app.utils.security import sanitize_log_message
from app.version import VERSION

logger = get_logger("社区应用")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(
    *,
    data_dir: Path | None = None,
    start_scheduler: bool = True,
    remote: RemoteAccess | None = None,
    external_state: bool = False,
) -> FastAPI:
    remote = remote or RemoteAccess.from_environment()
    remote_sessions = RemoteSessions(remote) if remote else None
    directory = data_dir or Path(
        os.environ.get("COMMUNITY_DATA_DIR", PROJECT_ROOT / "data")
    )
    diagnostics = Diagnostics(None if external_state else directory / "logs")
    if external_state:
        # 单用户 Durable Object 的日志跟随实例保留；控制台日志交由 Cloudflare 保存。
        logger.add(
            diagnostics.write, format="{message}", diagnose=False, backtrace=False
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if external_state:
            # Workers Durable Object 负责状态、定时触发与过期清理，不能每个 HTTP 请求重置。
            yield
            return
        log_sink = configure_file_logging(directory / "logs")
        capture_sink = logger.add(
            diagnostics.write, format="{message}", diagnose=False, backtrace=False
        )
        scheduler = None
        try:
            state.initialize(directory)
            logger.info(f"更好的MAS工具包 {VERSION} 启动，账号数={len(state.accounts)}")
            scheduler = (
                asyncio.create_task(runtime.auto_loop()) if start_scheduler else None
            )
            yield
        except Exception:
            logger.exception("工具启动或生命周期异常")
            raise
        finally:
            kuro_login.clear_sessions()
            miyoushe_missions.clear()
            if scheduler is not None:
                scheduler.cancel()
                await asyncio.gather(scheduler, return_exceptions=True)
            logger.info("工具后端已关闭")
            logger.remove(capture_sink)
            logger.remove(log_sink)

    app = FastAPI(title="更好的MAS工具包", version=VERSION, lifespan=lifespan)
    app.state.diagnostics = diagnostics
    app.state.session_key = secrets.token_urlsafe(32)
    allowed_hosts = ["localhost", "127.0.0.1", "[::1]"]
    if remote:
        allowed_hosts.append(urlsplit(remote.origin).hostname)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @app.middleware("http")
    async def local_session(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            expected_origin = (
                remote.origin if remote else f"http://{request.headers.get('host')}"
            )
            if origin and origin.rstrip("/") != expected_origin:
                return JSONResponse(
                    {"code": 403, "status": "error", "message": "请求来源不受支持"},
                    status_code=403,
                )
            key = request.headers.get("x-community-session", "")
            valid = (
                remote_sessions.valid(key)
                if remote_sessions
                else hmac.compare_digest(key.encode(), app.state.session_key.encode())
            )
            if request.url.path != "/api/session" and not valid:
                return JSONResponse(
                    {
                        "code": 401,
                        "status": "error",
                        "message": "会话已失效，请刷新页面重新登录",
                    },
                    status_code=401,
                )
        response = await call_next(request)
        if request.url.path.startswith(("/api/", "/captcha.")):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://doc.auto-mas.top; font-src 'self' data:; "
            "connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        if request.url.path == "/captcha.html":
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self' 'unsafe-eval' 'unsafe-inline' https://*.geetest.com https://*.geevisit.com https://*.gsensebot.com http://*.geetest.com http://*.geevisit.com http://*.gsensebot.com; "
                "style-src 'self' 'unsafe-inline' https://*.geetest.com https://*.geevisit.com https://*.gsensebot.com; img-src data: blob: https://*.geetest.com https://*.geevisit.com https://*.gsensebot.com http://*.geetest.com http://*.geevisit.com http://*.gsensebot.com; "
                "connect-src https://*.geetest.com https://*.geevisit.com https://*.gsensebot.com http://*.geetest.com http://*.geevisit.com http://*.gsensebot.com; frame-src https://*.geetest.com; "
                "base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
            )
        return response

    @app.middleware("http")
    async def trace_request(request: Request, call_next):
        request_id = secrets.token_hex(6)
        request.state.request_id = request_id
        path = request.url.path
        tracked = (
            path.startswith("/api/")
            and not path.startswith("/api/logs")
            and path != "/api/status"
        )
        started = monotonic()
        with logger.contextualize(requestId=request_id):
            if tracked:
                logger.info(f"开始 {request.method} {path}")
            try:
                response = await call_next(request)
            except Exception:
                logger.exception(f"{request.method} {path} 未完成")
                response = JSONResponse(
                    {
                        "code": 500,
                        "status": "error",
                        "message": f"操作未完成，请查看日志（编号 {request_id}）",
                    },
                    status_code=500,
                    headers={"Cache-Control": "no-store"},
                )
            response.headers["X-Request-ID"] = request_id
            if tracked or response.status_code >= 400:
                elapsed = int((monotonic() - started) * 1000)
                logger.log(
                    "WARNING" if response.status_code >= 400 else "INFO",
                    f"完成 {request.method} {path} HTTP={response.status_code} 耗时={elapsed}ms",
                )
            return response

    @app.get("/healthz", include_in_schema=False)
    async def health():
        return {
            "status": "ok",
            "application": "better-mas-community",
            "version": VERSION,
        }

    @app.get(
        "/api/session",
        response_model=SessionOut,
        operation_id="getSession",
        tags=["Session"],
    )
    async def session():
        return SessionOut(
            loginRequired=bool(remote), key="" if remote else app.state.session_key
        )

    @app.post(
        "/api/session",
        response_model=SessionOut,
        operation_id="loginSession",
        tags=["Session"],
    )
    async def login_session(body: SessionLoginIn, request: Request):
        if remote_sessions is None:
            return SessionOut(key=app.state.session_key)
        key = remote_sessions.login(
            body.password.get_secret_value(),
            request.client.host if request.client else "unknown",
        )
        return SessionOut(key=key)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _error: RequestValidationError):
        # ValidationError 的 input 可能包含密码，仅读取字段位置与错误类型。
        issues = [
            {"field": list(item["loc"]), "type": item["type"]}
            for item in _error.errors()
        ]
        logger.warning(f"请求字段校验失败：{issues}")
        return JSONResponse(
            {
                "code": 422,
                "status": "error",
                "message": "提交的数据不符合要求，请检查后重试",
            },
            status_code=422,
        )

    @app.exception_handler(ValueError)
    async def value_error(_request: Request, error: ValueError):
        reason = sanitize_log_message(str(error))
        logger.warning(reason)
        return JSONResponse(
            {
                "code": 400,
                "status": "error",
                "message": f"{reason}（日志编号 {_request.state.request_id}）",
            },
            status_code=400,
        )

    async def conflict(_request: Request, error: RuntimeError):
        return JSONResponse(
            {"code": 409, "status": "error", "message": str(error)}, status_code=409
        )

    app.add_exception_handler(CommunitySignInProgressError, conflict)
    app.add_exception_handler(CommunityActivityInProgressError, conflict)

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, error: Exception):
        logger.opt(exception=error).error("请求未完成")
        return JSONResponse(
            {"code": 500, "status": "error", "message": "操作未完成，请稍后重试"},
            status_code=500,
        )

    # 非首屏路由延迟 import，避免 WASM 引擎启动时全量加载平台协议模块。
    from app.api.cloud import router as cloud_router
    from app.api.diagnostics import router as diagnostics_router
    from app.api.gacha import router as gacha_router
    from app.api.kuro_login import router as kuro_login_router
    from app.api.mas import router as mas_router
    from app.api.miyoushe_missions import router as miyoushe_missions_router

    app.include_router(router)
    app.include_router(cloud_router)
    app.include_router(diagnostics_router)
    app.include_router(gacha_router)
    app.include_router(mas_router)
    app.include_router(kuro_login_router)
    app.include_router(miyoushe_missions_router)
    frontend = Path(os.environ.get("COMMUNITY_WEB_DIR", PROJECT_ROOT / "frontend/dist"))
    if not external_state and frontend.is_dir():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

        @app.get("/captcha.{extension}", include_in_schema=False)
        async def captcha_asset(extension: str):
            if extension not in {"html", "js", "css"}:
                return JSONResponse({"message": "资源不存在"}, status_code=404)
            return FileResponse(frontend / f"captcha.{extension}")

        @app.get("/", include_in_schema=False)
        async def index():
            return FileResponse(frontend / "index.html")

    return app


app = create_app()
