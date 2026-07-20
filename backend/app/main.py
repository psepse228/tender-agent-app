from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse

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

INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / "index.html"


@app.get("/", include_in_schema=False)
def serve_index() -> FileResponse:
    # No cache-control means browsers (and Telegram's in-app WebView
    # especially) apply their own heuristic freshness and can silently serve
    # a stale copy of the Mini App shell for a long time after a deploy.
    # This is a shell that changes on every ship -- never let it be cached.
    return FileResponse(
        INDEX_HTML_PATH,
        headers={"Cache-Control": "no-store, must-revalidate"},
    )
