"""
Админ-эндпоинт: полное удаление всех данных и кода проекта (только по секрету).
Вызывается ботом после подтверждения пользователем с id 1338143348.
Эндпоинт /logs — выдача файла логов сайта (для того же пользователя через бота).
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import PlainTextResponse

from backend.database import get_db_path
from backend.logging_config import get_logger, SITE_LOG_FILE

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
