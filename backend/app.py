"""FastAPI app: API REST + estáticos + bootstrap (migrations, seed, purge)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import auth, db, seed
from .routes import (
    auth_routes,
    billing,
    campaigns,
    conversations,
    dashboard,
    invites,
    leads,
    lgpd,
    media,
    notes,
    public,
    push,
    stores,
    tags,
    vehicles,
    whatsapp,
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
        return {"ok": True, "database": db.get_db_info()}

    # --- Painel Administrativo (/admin) --------------------------------------
    @app.get("/admin", include_in_schema=False)
    def admin_redirect():
        return RedirectResponse(url="/admin/", status_code=301)

    @app.get("/sistema", include_in_schema=False)
    @app.get("/painel", include_in_schema=False)
    def aliases_admin():
        return RedirectResponse(url="/admin/", status_code=307)

    app.mount("/admin", StaticFiles(directory=str(STATIC_ROOT), html=True), name="admin")

    # --- Multiatendimento Mobile PWA e Service Worker -----------------------
    @app.get("/atendimento", include_in_schema=False)
    def atendimento_redirect():
        return RedirectResponse(url="/atendimento.html", status_code=301)

    @app.get("/atendimento.html", include_in_schema=False)
    def get_atendimento():
        return FileResponse(STATIC_ROOT / "atendimento.html")

    @app.get("/sw.js", include_in_schema=False)
    def get_sw():
        return FileResponse(STATIC_ROOT / "sw.js", media_type="application/javascript")

    @app.get("/manifest.json", include_in_schema=False)
    def get_manifest():
        return FileResponse(STATIC_ROOT / "manifest.json", media_type="application/manifest+json")

    # --- Retrocompatibilidade /portal ---------------------------------------
    public_root = STATIC_ROOT / "public"
    public_assets = public_root / "assets"
    if public_assets.exists():
        app.mount("/portal/assets", StaticFiles(directory=str(public_assets)), name="portal_assets_compat")

    @app.get("/portal", include_in_schema=False)
    @app.get("/portal/", include_in_schema=False)
    def redirect_portal_root():
        return RedirectResponse(url="/", status_code=301)

    @app.get("/portal/{file_path:path}", include_in_schema=False)
    def redirect_portal_path(file_path: str):
        return RedirectResponse(url=f"/{file_path}", status_code=301)

    # --- Portal Público na Raiz (/) -----------------------------------------
    if public_root.exists():
        @app.get("/", include_in_schema=False)
        def public_home():
            return FileResponse(public_root / "index.html")

        app.mount("/", StaticFiles(directory=str(public_root), html=True), name="public_portal")

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
