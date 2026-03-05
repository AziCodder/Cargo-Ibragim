"""
Настройка логирования для backend (сайта).
Логи пишутся в logs/site.log в корне проекта.
"""
import logging
import sys
from pathlib import Path

# Корень проекта: backend/logging_config.py -> parent = backend -> parent = корень
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
SITE_LOG_FILE = LOGS_DIR / "site.log"

# Имя логгера для backend
LOGGER_NAME = "site"


def setup_logging() -> logging.Logger:
    """Создаёт и настраивает логгер, пишет в файл и в консоль."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(SITE_LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Возвращает логгер. Если name передан — дочерний от LOGGER_NAME."""
    if name:
        return logging.getLogger(f"{LOGGER_NAME}.{name}")
    return logging.getLogger(LOGGER_NAME)
