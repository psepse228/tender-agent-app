from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.routers import auth_google, favorites, health, profile, profile_chat, refresh, tenders

app = FastAPI(title="Tender Agent Backend")
app.include_router(health.router)
app.include_router(tenders.router)
app.include_router(refresh.router)
app.include_router(profile.router)
app.include_router(profile_chat.router)
app.include_router(auth_google.router)
app.include_router(favorites.router)

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
