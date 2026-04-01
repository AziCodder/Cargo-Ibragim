import os
import shutil
from pathlib import Path

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

from backend.database import init_db, get_db_path
from backend.routers import shipments, backup, clients, admin, groups
from backend.routers import auth as auth_router
from backend.logging_config import setup_logging, get_logger

# Логирование для сайта (backend)
setup_logging()
log = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Backend started. Clients API: /api/clients, /api/clients/register")
    yield
    log.info("Backend shutting down...")

app = FastAPI(title="Cargo Tracking API", lifespan=lifespan)

BACKUPS_DIR = Path(__file__).parent / "backups"
AUTO_BACKUP_FILENAME = "cargo_auto.db"


def _auto_backup():
    """Авто-копия раз в 30 мин: при настроенном S3 — загрузка в S3 (backups/auto/cargo.db), иначе — локально."""
    try:
        from backend.services.s3_backup import upload_auto_backup_to_s3, is_s3_configured
        if is_s3_configured():
            upload_auto_backup_to_s3()
            log.debug("Auto backup: uploaded to S3")
            return
    except Exception as e:
        log.warning("Auto backup S3 failed: %s", e)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUPS_DIR / AUTO_BACKUP_FILENAME
    shutil.copy2(get_db_path(), dest)
    log.debug("Auto backup: saved to %s", dest)


scheduler = BackgroundScheduler()
scheduler.add_job(_auto_backup, "interval", minutes=30)
scheduler.start()
_auto_backup()

# CORS: локальная разработка + при необходимости домен продакшена из .env (через запятую)
_cors = ["http://localhost:5173", "http://127.0.0.1:5173"]
_extra = os.getenv("CORS_ORIGINS", "").strip()
if _extra:
    _cors.extend(o.strip() for o in _extra.split(",") if o.strip())
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

app.include_router(auth_router.router)
app.include_router(shipments.router)
app.include_router(backup.router)
app.include_router(clients.router)
app.include_router(admin.router)
app.include_router(groups.router)

UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/api/health")
def health():
    return {"status": "ok"}
