from fastapi import FastAPI

from app.routers import health, profile, profile_chat, refresh, tenders

app = FastAPI(title="Tender Agent Backend")
app.include_router(health.router)
app.include_router(tenders.router)
app.include_router(refresh.router)
app.include_router(profile.router)
app.include_router(profile_chat.router)
