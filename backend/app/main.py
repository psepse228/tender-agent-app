from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="Tender Agent Backend")
app.include_router(health.router)
