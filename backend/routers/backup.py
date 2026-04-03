import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import get_db_path, init_db


class RestoreS3Request(BaseModel):
    prefix: str

router = APIRouter(prefix="/api", tags=["backup"])
BASE_DIR = Path(__file__).parent.parent
DB_PATH = Path(get_db_path())
BACKUPS_DIR = BASE_DIR / "backups"
MAX_BACKUPS = 7


def _ensure_backups_dir():
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/backup")
def create_backup():
    """Создаёт бэкап: при настроенном S3 — только в S3; иначе — локально."""
    try:
        from backend.services.s3_backup import backup_to_s3, is_s3_configured
        if is_s3_configured():
            result = backup_to_s3()
            return {"ok": True, "storage": "s3", "prefix": result["prefix"], "timestamp": result["timestamp"]}
    except Exception:
        pass
    _ensure_backups_dir()
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    dest = BACKUPS_DIR / f"cargo_{ts}.db"
    shutil.copy2(DB_PATH, dest)
    return {"filename": dest.name, "path": str(dest), "storage": "local"}


AUTO_BACKUP_FILENAME = "cargo_auto.db"


@router.get("/backups")
def list_backups():
    """Список локальных бэкапов. При настроенном S3 локальные не создаются — список бэкапов в S3 через GET /backups/s3."""
    try:
        from backend.services.s3_backup import is_s3_configured
        if is_s3_configured():
            return {"storage": "s3", "backups": [], "path": None}
    except Exception:
        pass
    _ensure_backups_dir()
    files = list(BACKUPS_DIR.glob("cargo_*.db"))
    files.sort(key=lambda p: (0 if p.name == AUTO_BACKUP_FILENAME else 1, -p.stat().st_mtime))
    backups = []
    for f in files:
        item = {"filename": f.name, "size": f.stat().st_size}
        if f.name == AUTO_BACKUP_FILENAME:
            item["label"] = "Авто"
        backups.append(item)
    return {
        "storage": "local",
        "path": str(BACKUPS_DIR.resolve()),
        "backups": backups,
    }


@router.post("/backup/s3")
def create_s3_backup():
    """Ручной бэкап в S3 (Hostkey). Создаёт папку backups/YYYY-MM-DD_HH-mm с БД и uploads."""
    try:
        from backend.services.s3_backup import backup_to_s3, is_s3_configured

        if not is_s3_configured():
            raise HTTPException(
                status_code=503,
                detail="S3 не настроен. Задайте S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET в .env",
            )
        result = backup_to_s3()
        return result
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка S3: {e}")


@router.get("/backup/s3/status")
def s3_backup_status():
    """Проверка: настроен ли S3."""
    try:
        from backend.services.s3_backup import is_s3_configured

        return {"configured": is_s3_configured()}
    except Exception:
        return {"configured": False}


@router.get("/backups/s3")
def list_s3_backups():
    """Список бэкапов в S3 (для выбора при восстановлении)."""
    try:
        from backend.services.s3_backup import list_backups_in_s3, is_s3_configured

        if not is_s3_configured():
            raise HTTPException(
                status_code=503,
                detail="S3 не настроен. Задайте S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET в .env",
            )
        backups = list_backups_in_s3()
        return {"backups": backups}
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backups/s3/restore")
def restore_from_s3(data: RestoreS3Request):
    """Восстановить базу и uploads из бэкапа в S3. Тело: {"prefix": "2025-03-03_14-30"}."""
    prefix = data.prefix.strip()
    if ".." in prefix or "/" in prefix.strip("/"):
        raise HTTPException(status_code=400, detail="Недопустимый prefix")
    try:
        from backend.services.s3_backup import restore_from_s3 as do_restore, is_s3_configured

        if not is_s3_configured():
            raise HTTPException(
                status_code=503,
                detail="S3 не настроен.",
            )
        result = do_restore(prefix)
        init_db()
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backups/restore/{filename}")
def restore_backup(filename: str):
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Недопустимое имя файла")
    src = BACKUPS_DIR / filename
    if not src.exists():
        raise HTTPException(status_code=404, detail="Резервная копия не найдена")
    shutil.copy2(src, DB_PATH)
    init_db()
    return {"ok": True, "message": "База данных восстановлена"}
