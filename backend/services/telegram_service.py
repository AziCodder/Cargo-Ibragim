import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BASE_DIR = Path(__file__).parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"


def get_chat_id_for_shipment(shipment: dict) -> str | None:
    """Возвращает chat_id для уведомления: из клиента накладной или fallback."""
    client_id = shipment.get("client_id")
    if client_id:
        import sqlite3
        db_path = BASE_DIR / "cargo.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT telegram_chat_id FROM clients WHERE id = ?",
            (client_id,),
        ).fetchone()
        conn.close()
        if row and row["telegram_chat_id"]:
            return row["telegram_chat_id"]
    return DEFAULT_CHAT_ID


def _escape_html(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _shipping_type_label(st: str) -> str:
    labels = {"1_7_days": "1-7 дней", "15_20_days": "15-20 дней", "20_30_days": "20-30 дней"}
    return labels.get(st or "", (st or "").replace("_", "-"))


def _format_shipment_dispatch(s: dict) -> str:
    lines = [
        "📦 <b>Уведомление об отправке</b>",
        "",
        f"<b>Трекинг:</b> {_escape_html(s.get('tracking', ''))}",
        f"<b>Дата отправления:</b> {_escape_html(str(s.get('dispatch_date', '')))}",
        f"<b>Срок доставки:</b> {_escape_html(_shipping_type_label(s.get('shipping_type', '')))}",
        f"<b>Вес:</b> {s.get('weight', 0)} кг",
        f"<b>Сумма к оплате:</b> {s.get('amount_to_pay', 0)}",
        "",
        f"<b>Список товара:</b>",
        _escape_html(s.get("product_list", "") or "—"),
    ]
    return "\n".join(lines)


def _format_shipment_delivery(s: dict) -> str:
    lines = [
        "✅ <b>Уведомление о прибытии</b>",
        "",
        f"<b>Трекинг:</b> {_escape_html(s.get('tracking', ''))}",
        f"<b>Вес:</b> {s.get('weight', 0)} кг",
        f"<b>Сумма к оплате:</b> {s.get('amount_to_pay', 0)}",
        "",
        f"<b>Список товара:</b>",
        _escape_html(s.get("product_list", "") or "—"),
    ]
    return "\n".join(lines)


def _iter_attachments(shipment_id: str, s: dict):
    """
    Итератор по вложениям накладной. Возвращает (путь к файлу, имя файла).
    Поддерживает локальные /uploads/ и файлы в S3 (ключ shipments/...).
    """
    import tempfile
    for f in [s.get("file1"), s.get("file2"), s.get("file3")]:
        if not f:
            continue
        if f.startswith("/uploads/"):
            full = UPLOADS_DIR / f.replace("/uploads/", "")
            if full.exists():
                yield full, full.name
        elif f.startswith("shipments/") or f.startswith("shipment/"):
            try:
                from backend.services.s3_storage import download_to_path
                suffix = os.path.splitext(f)[1] or ""
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.close()
                    download_to_path(f, tmp.name)
                    yield tmp.name, os.path.basename(f) or "file" + suffix
            except Exception:
                continue


def _get_file_paths(shipment_id: str, s: dict) -> list:
    """Список путей к файлам для отправки (локальные или временные после скачивания из S3)."""
    paths = []
    for path, _ in _iter_attachments(shipment_id, s):
        paths.append(path)
    return paths


def send_dispatch_notification(shipment: dict) -> bool:
    chat_id = get_chat_id_for_shipment(shipment)
    if not BOT_TOKEN or not chat_id:
        return False
    text = _format_shipment_dispatch(shipment)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    with httpx.Client() as client:
        r = client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
        if r.status_code != 200:
            return False
        for fp, name in _iter_attachments(shipment["id"], shipment):
            doc_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
            try:
                with open(fp, "rb") as f:
                    client.post(doc_url, data={"chat_id": chat_id}, files={"document": (name, f)})
            finally:
                if not str(fp).startswith(str(UPLOADS_DIR)):
                    try:
                        os.unlink(fp)
                    except Exception:
                        pass
    return True


def send_delivery_notification(shipment: dict) -> bool:
    chat_id = get_chat_id_for_shipment(shipment)
    if not BOT_TOKEN or not chat_id:
        return False
    text = _format_shipment_delivery(shipment)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    with httpx.Client() as client:
        r = client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
        if r.status_code != 200:
            return False
        for fp, name in _iter_attachments(shipment["id"], shipment):
            doc_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
            try:
                with open(fp, "rb") as f:
                    client.post(doc_url, data={"chat_id": chat_id}, files={"document": (name, f)})
            finally:
                if not str(fp).startswith(str(UPLOADS_DIR)):
                    try:
                        os.unlink(fp)
                    except Exception:
                        pass
    return True
