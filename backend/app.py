"""FastAPI app: API REST + estáticos + bootstrap (migrations, seed, purge)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import auth, db, seed
from .routes import (
    auth_routes,
    billing,
    conversations,
    invites,
    leads,
    lgpd,
    media,
    notes,
    public,
    stores,
    tags,
    vehicles,
    whatsapp,
    dashboard,
    push,
    campaigns,
)
from .routes import events as events_route
from .settings import settings

STATIC_ROOT = Path(__file__).resolve().parent.parent


def boot() -> None:
    applied = db.run_migrations()
    if applied:
        print(f"Migrations aplicadas: {', '.join(applied)}")
    if seed.run():
        print("Seed inicial carregado (senha demo: demo123).")
    if seed.seed_multiatendimento():
        print("Seed multiatendimento (Tex) carregado.")
    auth.purge_expired()


@asynccontextmanager
async def lifespan(_: FastAPI):
    boot()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Formula OS", version="0.3.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def _http_exc(_request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(_request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": "Payload inválido", "details": exc.errors()})

    app.include_router(auth_routes.router, prefix="/api", tags=["auth"])
    app.include_router(stores.router,      prefix="/api", tags=["stores"])
    app.include_router(vehicles.router,    prefix="/api", tags=["vehicles"])
    app.include_router(leads.router,       prefix="/api", tags=["leads"])
    app.include_router(conversations.router, prefix="/api", tags=["conversations"])
    # whatsapp router já traz seus próprios prefixos (/api/... e /webhooks/...)
    app.include_router(whatsapp.router, tags=["whatsapp"])
    app.include_router(events_route.router, tags=["events"])
    app.include_router(billing.router, tags=["billing"])
    app.include_router(invites.router, tags=["invites"])
    app.include_router(lgpd.router, tags=["lgpd"])
    app.include_router(public.router, tags=["public"])
    app.include_router(tags.router, tags=["tags"])
    app.include_router(notes.router, tags=["notes"])
    app.include_router(media.router, tags=["media"])
    app.include_router(dashboard.router, tags=["dashboard"])
    app.include_router(push.router, tags=["push"])
    app.include_router(campaigns.router, tags=["campaigns"])

    @app.get("/api/health", tags=["health"])
    def health():
        return {"ok": True, "database": db.DB_PATH.name}

    # --- Portal público (cliente final) montado em /portal -------------------
    public_root = STATIC_ROOT / "public"
    if public_root.exists():
        @app.get("/portal", include_in_schema=False)
        def redirect_portal():
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/portal/")
            
        app.mount("/portal", StaticFiles(directory=str(public_root), html=True), name="portal")

    # SPA admin + estáticos: index.html na raiz; demais arquivos via StaticFiles.
    @app.get("/", include_in_schema=False)
    def root():
        return FileResponse(STATIC_ROOT / "index.html")

    app.mount("/", StaticFiles(directory=str(STATIC_ROOT), html=True), name="static")

    return app


app = create_app()


def run() -> None:
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )
