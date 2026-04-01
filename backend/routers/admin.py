"""
Админ-эндпоинты:
- Логи и полное удаление (по X-Admin-Secret, для бота)
- CRUD пользователей (по JWT, только admin)
"""
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Header, HTTPException, Depends
from fastapi.responses import PlainTextResponse

from backend.auth import hash_password, require_admin
from backend.database import get_db, get_db_path
from backend.logging_config import get_logger, SITE_LOG_FILE
from backend.models import UserCreate, UserUpdate, UserResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])
log = get_logger("admin")

# Корень проекта (backend/routers/admin.py -> backend -> корень)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _get_secret() -> str:
    return (os.getenv("DELETE_ALL_SECRET") or "").strip()


def _check_admin_secret(x_admin_secret: str | None) -> bool:
    secret = _get_secret()
    return bool(secret and x_admin_secret == secret)


@router.get("/logs", response_class=PlainTextResponse)
def get_site_logs(x_admin_secret: str | None = Header(None, alias="X-Admin-Secret")):
    """
    Возвращает содержимое файла логов сайта (site.log).
    Доступ только с заголовком X-Admin-Secret. Вызывается ботом по команде /logs для user 1338143348.
    """
    if not _check_admin_secret(x_admin_secret):
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    if not SITE_LOG_FILE.exists():
        return "# Лог-файл сайта ещё не создан.\n"
    try:
        return SITE_LOG_FILE.read_text(encoding="utf-8")
    except Exception as e:
        log.exception("Ошибка чтения логов: %s", e)
        raise HTTPException(status_code=500, detail="Ошибка чтения логов")


BOT_LOG_FILE = PROJECT_ROOT / "logs" / "bot.log"


@router.get("/logs/site", response_class=PlainTextResponse)
def get_site_logs_jwt(lines: int = 500, _admin=Depends(require_admin)):
    """Логи бэкенда — для отображения на сайте (JWT auth)."""
    if not SITE_LOG_FILE.exists():
        return "# Лог-файл бэкенда ещё не создан.\n"
    try:
        all_lines = SITE_LOG_FILE.read_text(encoding="utf-8").splitlines()
        return "\n".join(all_lines[-lines:])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка чтения логов: {e}")


@router.get("/logs/bot", response_class=PlainTextResponse)
def get_bot_logs_jwt(lines: int = 500, _admin=Depends(require_admin)):
    """Логи бота — для отображения на сайте (JWT auth)."""
    if not BOT_LOG_FILE.exists():
        return "# Лог-файл бота ещё не создан.\n"
    try:
        all_lines = BOT_LOG_FILE.read_text(encoding="utf-8").splitlines()
        return "\n".join(all_lines[-lines:])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка чтения логов: {e}")


@router.post("/delete-all-project")
def delete_all_project(x_admin_secret: str | None = Header(None, alias="X-Admin-Secret")):
    """
    Полное удаление: S3, БД, весь код проекта (включая этот).
    Вызывается только ботом с заголовком X-Admin-Secret после подтверждения пользователем.
    """
    if not _check_admin_secret(x_admin_secret):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    log.warning("delete_all_project: запрос на полное удаление выполнен")

    try:
        # 1) Очистить всё хранилище S3
        try:
            from backend.services.s3_storage import clear_entire_bucket, is_s3_configured
            if is_s3_configured():
                clear_entire_bucket()
        except Exception:
            pass  # продолжаем даже при ошибке S3

        # 2) Удалить БД
        try:
            db_path = get_db_path()
            if os.path.isfile(db_path):
                os.remove(db_path)
        except Exception:
            pass

        # 3) Создать скрипт в /tmp, который удалит весь каталог проекта и себя
        try:
            project_dir = str(PROJECT_ROOT)
            script = f'''#!/bin/bash
rm -rf "{project_dir}"
rm -f /tmp/wipe_ibra_*.sh
'''
            fd, script_path = tempfile.mkstemp(prefix="wipe_ibra_", suffix=".sh", dir="/tmp")
            try:
                os.write(fd, script.encode())
            finally:
                os.close(fd)
            os.chmod(script_path, 0o700)
            subprocess.Popen(
                ["/bin/bash", script_path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass

        return {"ok": True, "message": "Удаление запущено."}
    finally:
        os._exit(0)


# ---------------------------------------------------------------------------
# Управление пользователями (только admin)
# ---------------------------------------------------------------------------

@router.get("/users", response_model=List[UserResponse])
def list_users(_admin=Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, username, role, client_id, created_at FROM users ORDER BY created_at ASC"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "username": r["username"],
            "role": r["role"],
            "client_id": r["client_id"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(data: UserCreate, _admin=Depends(require_admin)):
    if data.role not in ("admin", "client"):
        raise HTTPException(status_code=400, detail="Роль должна быть 'admin' или 'client'")
    with get_db() as conn:
        existing = conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (data.username,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")
        user_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, client_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, data.username, hash_password(data.password), data.role, data.client_id, created_at),
        )
    log.info("Создан пользователь username=%s role=%s", data.username, data.role)
    return {
        "id": user_id,
        "username": data.username,
        "role": data.role,
        "client_id": data.client_id,
        "created_at": created_at,
    }


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: str, data: UserUpdate, _admin=Depends(require_admin)):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        if data.role is not None and data.role not in ("admin", "client"):
            raise HTTPException(status_code=400, detail="Роль должна быть 'admin' или 'client'")
        new_hash = hash_password(data.password) if data.password else row["password_hash"]
        new_role = data.role if data.role is not None else row["role"]
        new_client_id = data.client_id if data.client_id is not None else row["client_id"]
        conn.execute(
            "UPDATE users SET password_hash=?, role=?, client_id=? WHERE id=?",
            (new_hash, new_role, new_client_id, user_id),
        )
    log.info("Обновлён пользователь id=%s", user_id)
    return {
        "id": user_id,
        "username": row["username"],
        "role": new_role,
        "client_id": new_client_id,
        "created_at": row["created_at"],
    }


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, _admin=Depends(require_admin)):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        # Удаляем и бот-сессии этого пользователя
        conn.execute("DELETE FROM bot_sessions WHERE user_id = ?", (user_id,))
    log.info("Удалён пользователь id=%s username=%s", user_id, row["username"])
    return None
