from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import (
    auth_google,
    favorites,
    health,
    legal,
    profile,
    profile_chat,
    refresh,
    sources,
    stats,
    telegram_link,
    tenders,
)

app = FastAPI(title="Tender Agent Backend")
app.include_router(health.router)
app.include_router(tenders.router)
app.include_router(refresh.router)
app.include_router(profile.router)
app.include_router(profile_chat.router)
app.include_router(auth_google.router)
app.include_router(favorites.router)
app.include_router(legal.router)
app.include_router(sources.router)
app.include_router(stats.router)
app.include_router(telegram_link.router)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Deliberately no X-Frame-Options / frame-ancestors -- this app is a
    # Telegram Mini App and MUST be embeddable inside Telegram's own webview
    # iframe. Adding clickjacking protection here would break the product's
    # primary distribution channel.
    return response

DIST_DIR = Path(__file__).resolve().parent.parent / "dist"
INDEX_HTML_PATH = DIST_DIR / "index.html"

# The React app (frontend/, built by `npm run build` into backend/dist/ --
# see frontend/vite.config.ts) ships its hashed JS/CSS under dist/assets/.
# Those filenames change every build, so they're safe to cache forever;
# index.html itself is served separately below with no-store instead.
#
# Guarded by exists(): dist/ is a build artifact (gitignored, produced by the
# frontend's own build step), not something committed to the repo, so it's
# absent for the test suite and any plain `uvicorn app.main:app` run that
# hasn't built the frontend first. StaticFiles(check_dir=True) would raise at
# import time otherwise, breaking every test that imports this module.
if (DIST_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")


def _serve_index() -> FileResponse:
    # No cache-control means browsers (and Telegram's in-app WebView
    # especially) apply their own heuristic freshness and can silently serve
    # a stale copy of the Mini App shell for a long time after a deploy.
    # This is a shell that changes on every ship -- never let it be cached.
    return FileResponse(
        INDEX_HTML_PATH,
        headers={"Cache-Control": "no-store, must-revalidate"},
    )


@app.get("/", include_in_schema=False)
def serve_index() -> FileResponse:
    return _serve_index()


# SPA client-side routing fallback (react-router's BrowserRouter, e.g.
# /favorites, /favorites/<id>, /scout, /sources, /methodology) -- a hard
# refresh or deep link on any of those paths is still a real HTTP GET to
# FastAPI, which has no route for them; without this they'd 404 instead of
# handing back the same shell "/" gets, which then lets react-router take
# over client-side. Registered last so it only ever catches paths that
# every router/mount above has already declined -- notably including
# /api/*, so a genuinely unknown API path still 404s as JSON instead of
# silently returning the HTML shell.
@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa_fallback(full_path: str) -> FileResponse:
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404)
    return _serve_index()
