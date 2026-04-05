"""
Резервное копирование в S3 (Hostkey или любой S3-совместимый сервис).
Создаёт папку с датой/временем и загружает туда БД + все файлы из uploads.
"""
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from backend.database import get_db_path

BASE_DIR = Path(__file__).parent.parent
DB_PATH = Path(get_db_path())
UPLOADS_DIR = BASE_DIR / "uploads"

S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
S3_SECRET_KEY = os.getenv("S3_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_ENDPOINT = os.getenv("S3_ENDPOINT_URL") or os.getenv("S3_ENDPOINT")
S3_REGION = os.getenv("S3_REGION", "us-east-1")


def _get_s3_client():
    import boto3
    from botocore.config import Config

    if not all([S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET]):
        raise ValueError(
            "Задайте S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET в .env"
        )

    config = Config(
        signature_version="s3v4",
        retries={"max_attempts": 3},
        s3={"addressing_style": "path"} if S3_ENDPOINT else {},
    )
    client_kw = {
        "aws_access_key_id": S3_ACCESS_KEY,
        "aws_secret_access_key": S3_SECRET_KEY,
        "config": config,
        "region_name": S3_REGION,
    }
    if S3_ENDPOINT:
        client_kw["endpoint_url"] = S3_ENDPOINT.rstrip("/")

    return boto3.client("s3", **client_kw)


AUTO_BACKUP_PREFIX = "backups/new"


def upload_auto_backup_to_s3() -> None:
    """
    Загружает только БД в S3 в фиксированный ключ backups/auto/cargo.db (перезапись).
    Для авто-бэкапа раз в N минут — файлы накладных уже в S3, в бэкап кладём только БД.
    """
    if not DB_PATH.exists():
        return
    client = _get_s3_client()
    key = f"{AUTO_BACKUP_PREFIX}/cargo.db"
    client.upload_file(str(DB_PATH), S3_BUCKET, key)


def backup_to_s3() -> dict:
    """
    Создаёт папку в S3 с текущим состоянием: cargo.db + uploads/.
    Возвращает {"ok": True, "prefix": "backups/2025-03-03_14-30"} или raises.
    """
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    prefix = f"backups/{ts}"

    client = _get_s3_client()

    # 1. Загружаем БД
    if not DB_PATH.exists():
        raise FileNotFoundError(f"База не найдена: {DB_PATH}")
    db_key = f"{prefix}/cargo.db"
    client.upload_file(str(DB_PATH), S3_BUCKET, db_key)

    # 2. Загружаем uploads
    if UPLOADS_DIR.exists():
        for root, _, files in os.walk(UPLOADS_DIR):
            for f in files:
                local_path = Path(root) / f
                rel = local_path.relative_to(UPLOADS_DIR)
                s3_key = f"{prefix}/uploads/{rel.as_posix()}"
                client.upload_file(str(local_path), S3_BUCKET, s3_key)

    return {"ok": True, "prefix": prefix, "timestamp": ts}


def list_backups_in_s3() -> list:
    """
    Список бэкапов в S3 (папки под префиксом backups/).
    Возвращает [{"prefix": "2025-03-03_14-30", "key": "backups/2025-03-03_14-30"}, ...],
    отсортированный по ключу (новые выше).
    """
    client = _get_s3_client()
    prefix = "backups/"
    result = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix, Delimiter="/"):
        for common_prefix in page.get("CommonPrefixes", []):
            key = common_prefix["Prefix"].rstrip("/")
            short = key.replace(prefix, "").rstrip("/")
            if short:
                result.append({"prefix": short, "key": key})
    result.sort(key=lambda x: x["key"], reverse=True)
    return result


def restore_from_s3(prefix: str) -> dict:
    """
    Восстанавливает базу и uploads из бэкапа S3 (backups/{prefix}/).
    Скачивает cargo.db в DB_PATH и uploads/ в UPLOADS_DIR.
    """
    import shutil
    import tempfile

    client = _get_s3_client()
    base = f"backups/{prefix.strip('/')}"
    db_key = f"{base}/cargo.db"

    # Проверяем наличие БД в бэкапе
    try:
        client.head_object(Bucket=S3_BUCKET, Key=db_key)
    except Exception as e:
        code = getattr(e, "response", {}).get("Error", {}).get("Code", "") if hasattr(e, "response") else ""
        if code in ("404", "NoSuchKey"):
            raise FileNotFoundError(f"Бэкап не найден в S3: {db_key}")
        raise

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_db = Path(tmpdir) / "cargo.db"
        client.download_file(S3_BUCKET, db_key, str(tmp_db))
        shutil.copy2(tmp_db, DB_PATH)

    # Восстанавливаем uploads из бэкапа (если есть)
    uploads_prefix = f"{base}/uploads/"
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=uploads_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            rel = key[len(uploads_prefix):].lstrip("/")
            if not rel:
                continue
            local_path = UPLOADS_DIR / rel
            local_path.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(S3_BUCKET, key, str(local_path))

    return {"ok": True, "message": "Восстановлено из S3", "prefix": prefix}


def is_s3_configured() -> bool:
    return bool(S3_ACCESS_KEY and S3_SECRET_KEY and S3_BUCKET)
