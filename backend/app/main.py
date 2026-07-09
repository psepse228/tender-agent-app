from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.routers import health, profile, profile_chat, refresh, tenders

app = FastAPI(title="Tender Agent Backend")
app.include_router(health.router)
app.include_router(tenders.router)
app.include_router(refresh.router)
app.include_router(profile.router)
app.include_router(profile_chat.router)

INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / "index.html"


@app.get("/", include_in_schema=False)
def serve_index() -> FileResponse:
    return FileResponse(INDEX_HTML_PATH)
