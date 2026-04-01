import os
import sqlite3
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BASE_DIR = Path(__file__).parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"


def get_chat_ids_for_shipment(shipment: dict) -> list[str]:
    """
    Возвращает список chat_id для уведомления:
    1. clients.telegram_chat_id клиента
    2. clients.group_chat_id клиента (если задан)
    3. Все bot_sessions.telegram_chat_id для данного client_id
    4. Все shipment_recipients.chat_id для данной накладной
    5. Fallback на DEFAULT_CHAT_ID если список пустой
    """
    chat_ids = set()
    db_path = BASE_DIR / "cargo.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        client_id = shipment.get("client_id")
        if client_id:
            row = conn.execute(
                "SELECT telegram_chat_id, group_chat_id FROM clients WHERE id = ?",
                (client_id,),
            ).fetchone()
            if row:
                if row["telegram_chat_id"]:
                    chat_ids.add(row["telegram_chat_id"])
                if row["group_chat_id"]:
                    chat_ids.add(row["group_chat_id"])
            # Добавить все активные bot-сессии для этого клиента
            sessions = conn.execute(
                "SELECT telegram_chat_id FROM bot_sessions WHERE client_id = ?",
                (client_id,),
            ).fetchall()
            for s in sessions:
                if s["telegram_chat_id"]:
                    chat_ids.add(s["telegram_chat_id"])

        # Дополнительные получатели, прикреплённые к конкретной накладной
        shipment_id = shipment.get("id")
        if shipment_id:
            recipients = conn.execute(
                "SELECT chat_id FROM shipment_recipients WHERE shipment_id = ?",
                (shipment_id,),
            ).fetchall()
            for r in recipients:
                if r["chat_id"]:
                    chat_ids.add(r["chat_id"])
    finally:
        conn.close()

    if not chat_ids and DEFAULT_CHAT_ID:
        chat_ids.add(DEFAULT_CHAT_ID)

    return list(chat_ids)


# Обратная совместимость — используется в некоторых местах
def get_chat_id_for_shipment(shipment: dict) -> str | None:
    ids = get_chat_ids_for_shipment(shipment)
    return ids[0] if ids else None


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


def _send_to_chat(client: httpx.Client, chat_id: str, text: str, shipment: dict):
    """Отправляет текст + вложения в один chat_id."""
    url_msg = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = client.post(url_msg, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
    if r.status_code != 200:
        return False
    doc_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    # Собираем вложения один раз для каждого chat_id
    for fp, name in _iter_attachments(shipment.get("id", ""), shipment):
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


def send_dispatch_notification(shipment: dict) -> bool:
    chat_ids = get_chat_ids_for_shipment(shipment)
    if not BOT_TOKEN or not chat_ids:
        return False
    text = _format_shipment_dispatch(shipment)
    any_ok = False
    with httpx.Client() as client:
        for chat_id in chat_ids:
            ok = _send_to_chat(client, chat_id, text, shipment)
            if ok:
                any_ok = True
    return any_ok


def send_delivery_notification(shipment: dict) -> bool:
    chat_ids = get_chat_ids_for_shipment(shipment)
    if not BOT_TOKEN or not chat_ids:
        return False
    text = _format_shipment_delivery(shipment)
    any_ok = False
    with httpx.Client() as client:
        for chat_id in chat_ids:
            ok = _send_to_chat(client, chat_id, text, shipment)
            if ok:
                any_ok = True
    return any_ok
