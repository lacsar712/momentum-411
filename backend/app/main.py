import logging
import time
import os
from datetime import date
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from app.core.config import settings
from app.db import init_db, get_session, check_db
from app.routers import router
from app.services.seed import seed_basic_data, seed_concept_data
from app.services.data_sync import sync_stock_list, sync_daily
from app.services.cache import redis_client
from app.models import Stock
from sqlmodel import select

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("momentum")

from app.services.scheduler import init_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Backend starting up")
    init_db()
    session = get_session()
    seed_basic_data(session)
    seed_concept_data(session)
    init_scheduler()
    yield
    logger.info("Backend shutting down")

app = FastAPI(
    title="Momentum A-Share System",
    description="Quantitative Trading System Backend",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(router)

upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")

@app.middleware("http")
async def request_timing(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000
    logger.info("request completed", extra={"path": request.url.path, "status_code": response.status_code, "duration_ms": round(duration, 2)})
    return response

@app.get("/")
async def root():
    return {"message": "欢迎使用 Momentum API", "docs": "/docs"}

@app.get("/health")
async def health_check():
    db_ok = check_db()
    redis_ok = False
    try:
        redis_ok = redis_client.ping()
    except Exception:
        pass

    overall = "healthy" if (db_ok and redis_ok) else "unhealthy"
    status_code = status.HTTP_200_OK if (db_ok and redis_ok) else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        content={
            "status": overall,
            "project": settings.PROJECT_NAME,
            "components": {
                "database": "healthy" if db_ok else "unhealthy",
                "redis": "healthy" if redis_ok else "unhealthy"
            }
        },
        status_code=status_code
    )
