#!/usr/bin/env python3
"""
Скрипт для cron: создаёт бэкап в S3.
Запуск: из корня проекта — python -m backend.scripts.s3_backup
Или: cd "ИБРА ПРОЕКТ" && python -m backend.scripts.s3_backup

Для cron (раз в день в 3:00):
0 3 * * * cd /path/to/ИБРА\ ПРОЕКТ && python -m backend.scripts.s3_backup >> /var/log/cargo_s3_backup.log 2>&1
"""
import sys
from pathlib import Path

# Добавляем корень проекта в path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    from backend.services.s3_backup import backup_to_s3, is_s3_configured

    if not is_s3_configured():
        print("Ошибка: S3 не настроен. Задайте S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET в .env")
        sys.exit(1)

    try:
        result = backup_to_s3()
        print(f"OK: {result.get('prefix', result)}")
        sys.exit(0)
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
