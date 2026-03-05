"""
Хранение файлов накладных в S3.
Файлы сохраняются в папке shipments/{shipment_id}/ с именем файла.
"""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
S3_SECRET_KEY = os.getenv("S3_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_ENDPOINT = os.getenv("S3_ENDPOINT_URL") or os.getenv("S3_ENDPOINT")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

PREFIX = "shipments"


def _get_s3_client():
    import boto3
    from botocore.config import Config

    if not all([S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET]):
        raise ValueError("S3 не настроен: задайте S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET")

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


def is_s3_configured() -> bool:
    return bool(S3_ACCESS_KEY and S3_SECRET_KEY and S3_BUCKET)


def upload_file(shipment_id: str, file_obj, filename: str, slot: Optional[int] = None) -> str:
    """
    Загружает файл в S3 в папку shipments/{shipment_id}/.
    slot: 1, 2 или 3 — слот файла (file1, file2, file3).
    Возвращает S3-ключ (для сохранения в БД).
    """
    ext = Path(filename).suffix or ""
    if slot is not None:
        safe_name = f"file{slot}"
    else:
        safe_name = Path(filename).stem or "file"
    key = f"{PREFIX}/{shipment_id}/{safe_name}{ext}"
    client = _get_s3_client()
    client.upload_fileobj(file_obj, S3_BUCKET, key)
    return key


def download_to_path(s3_key: str, local_path: str) -> None:
    """Скачивает файл из S3 в указанный локальный путь."""
    client = _get_s3_client()
    client.download_file(S3_BUCKET, s3_key, local_path)


def get_presigned_url(s3_key: str, expires_in: int = 3600) -> str:
    """Генерирует presigned URL для скачивания файла."""
    client = _get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": s3_key},
        ExpiresIn=expires_in,
    )


def delete_shipment_files(shipment_id: str) -> None:
    """Удаляет все файлы накладной из S3."""
    client = _get_s3_client()
    prefix = f"{PREFIX}/{shipment_id}/"
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        objs = page.get("Contents", [])
        if not objs:
            continue
        client.delete_objects(
            Bucket=S3_BUCKET,
            Delete={"Objects": [{"Key": o["Key"]} for o in objs]},
        )


def clear_entire_bucket() -> None:
    """Полностью очищает хранилище S3 (все объекты в бакете)."""
    client = _get_s3_client()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET):
        objs = page.get("Contents", [])
        if not objs:
            continue
        client.delete_objects(
            Bucket=S3_BUCKET,
            Delete={"Objects": [{"Key": o["Key"]} for o in objs]},
        )
