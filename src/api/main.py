from fastapi import FastAPI
from src.api.routes.health import router as health_router
from src.api.routes.market import router as market_router

app = FastAPI(title="Neuro Multi Agent Project")

app.include_router(health_router)
app.include_router(market_router)