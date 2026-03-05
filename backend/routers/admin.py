"""
Админ-эндпоинт: полное удаление всех данных и кода проекта (только по секрету).
Вызывается ботом после подтверждения пользователем с id 1338143348.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException

from backend.database import get_db_path

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Корень проекта (backend/routers/admin.py -> backend -> корень)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _get_secret() -> str:
    return (os.getenv("DELETE_ALL_SECRET") or "").strip()


@router.post("/delete-all-project")
def delete_all_project(x_admin_secret: str | None = Header(None, alias="X-Admin-Secret")):
    """
    Полное удаление: S3, БД, весь код проекта (включая этот).
    Вызывается только ботом с заголовком X-Admin-Secret после подтверждения пользователем.
    """
    secret = _get_secret()
    if not secret or x_admin_secret != secret:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    try:
        # 1) Очистить всё хранилище S3
        try:
            from backend.services.s3_storage import clear_entire_bucket, is_s3_configured
            if is_s3_configured():
                clear_entire_bucket()
        except Exception as e:
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
            # Запуск в фоне; процесс бэкенда завершится, скрипт продолжит и удалит всё
            subprocess.Popen(
                ["/bin/bash", script_path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            # На Windows или без /tmp — только выходим
            pass

        return {"ok": True, "message": "Удаление запущено."}
    finally:
        # 4) Завершить процесс после ответа
        os._exit(0)
