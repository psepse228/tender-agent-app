from fastapi import FastAPI

from app.routers import health, tenders

app = FastAPI(title="Tender Agent Backend")
app.include_router(health.router)
app.include_router(tenders.router)
