import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import RedirectResponse
from typing import Optional, List
from pydantic import BaseModel

from backend.auth import get_current_user, require_admin
from backend.database import get_db, row_to_shipment
from backend.logging_config import get_logger
from backend.models import ShipmentCreate, ShipmentUpdate, ShipmentResponse, Status, RecipientAdd, RecipientResponse
from backend.services.telegram_service import (
    send_dispatch_notification,
    send_delivery_notification,
    get_chat_ids_for_shipment,
)

router = APIRouter(prefix="/api/shipments", tags=["shipments"])
log = get_logger("shipments")
UPLOADS_DIR = Path(__file__).parent.parent / "uploads"


def _s3_available() -> bool:
    try:
        from backend.services.s3_storage import is_s3_configured
        return is_s3_configured()
    except Exception:
        return False


def _save_files(shipment_id: str, files: List[Optional[UploadFile]]) -> tuple:
    """Сохраняет файлы только в S3. Требует настройки S3."""
    if not _s3_available():
        raise HTTPException(
            status_code=503,
            detail="Хранение файлов настроено на S3. Задайте S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET в .env",
        )
    from backend.services.s3_storage import upload_file
    paths = [None, None, None]
    for i, f in enumerate(files[:3]):
        if f and f.filename:
            f.file.seek(0)
            key = upload_file(shipment_id, f.file, f.filename, slot=i + 1)
            paths[i] = key
    return tuple(paths)


def _get_shipment_by_id(shipment_id: str) -> dict:
    with get_db() as conn:
        row = conn.execute(
            """SELECT s.*, c.full_name as client_name
               FROM shipments s
               LEFT JOIN clients c ON s.client_id = c.id
               WHERE s.id = ?""",
            (shipment_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Накладная не найдена")
        return row_to_shipment(row)


def _check_shipment_access(shipment: dict, current_user: dict):
    """Проверяет доступ клиента к накладной. Admin — без ограничений."""
    if current_user["role"] == "admin":
        return
    if shipment.get("client_id") != current_user.get("client_id"):
        raise HTTPException(status_code=403, detail="Доступ запрещён")


@router.get("", response_model=List[ShipmentResponse])
def list_shipments(
    status: Optional[str] = None,
    sort: str = "dispatch_date",
    order: str = "desc",
    current_user: dict = Depends(get_current_user),
):
    with get_db() as conn:
        query = """SELECT s.*, c.full_name as client_name
                   FROM shipments s
                   LEFT JOIN clients c ON s.client_id = c.id"""
        params = []

        conditions = []
        if status == "closed":
            conditions.append("s.status IN (?, ?)")
            params.extend([Status.DELIVERED.value, Status.CANCELLED.value])
        elif status:
            conditions.append("s.status = ?")
            params.append(status)

        # Клиент видит только свои накладные
        if current_user["role"] == "client":
            conditions.append("s.client_id = ?")
            params.append(current_user.get("client_id"))

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        order_col = "s.dispatch_date" if sort == "dispatch_date" else "s.created_at"
        direction = "DESC" if order.lower() == "desc" else "ASC"
        query += f" ORDER BY {order_col} {direction}"
        rows = conn.execute(query, params).fetchall()
    return [row_to_shipment(r) for r in rows]


@router.get("/in-transit-by-telegram/{telegram_chat_id}", response_model=List[ShipmentResponse])
def list_in_transit_by_telegram(telegram_chat_id: str):
    """Накладные «в дороге» для клиента по его telegram_chat_id или bot_session."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT s.*, c.full_name as client_name
               FROM shipments s
               INNER JOIN clients c ON s.client_id = c.id
               WHERE (
                   c.telegram_chat_id = ?
                   OR c.id IN (SELECT client_id FROM bot_sessions WHERE telegram_chat_id = ?)
               )
               AND s.status = ?
               ORDER BY s.dispatch_date DESC""",
            (telegram_chat_id, telegram_chat_id, Status.IN_TRANSIT.value),
        ).fetchall()
    return [row_to_shipment(r) for r in rows]


@router.get("/by-tracking", response_model=ShipmentResponse)
def get_shipment_by_tracking(tracking: str, telegram_chat_id: str):
    """Поиск накладной по трекингу только среди заказов клиента с данным telegram_chat_id."""
    tracking = (tracking or "").strip()
    if not tracking:
        raise HTTPException(status_code=400, detail="Укажите трекинг")
    with get_db() as conn:
        row = conn.execute(
            """SELECT s.*, c.full_name as client_name
               FROM shipments s
               INNER JOIN clients c ON s.client_id = c.id
               WHERE (
                   c.telegram_chat_id = ?
                   OR c.id IN (SELECT client_id FROM bot_sessions WHERE telegram_chat_id = ?)
               )
               AND LOWER(TRIM(s.tracking)) = LOWER(?)""",
            (telegram_chat_id, telegram_chat_id, tracking),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Заказ не найден или не привязан к вашему аккаунту")
    return row_to_shipment(row)


@router.get("/cashback", response_model=List[ShipmentResponse])
def list_cashback_shipments(_admin=Depends(require_admin)):
    """Только для admin: накладные с датой получения для расчёта по кэшбеку."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT s.*, c.full_name as client_name
               FROM shipments s
               LEFT JOIN clients c ON s.client_id = c.id
               WHERE s.delivery_date IS NOT NULL AND s.delivery_date != ''
               ORDER BY s.calculated ASC, s.delivery_date ASC, s.created_at ASC""",
        ).fetchall()
    return [row_to_shipment(r) for r in rows]


@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_shipment(shipment_id: str, current_user: dict = Depends(get_current_user)):
    s = _get_shipment_by_id(shipment_id)
    _check_shipment_access(s, current_user)
    return s


def _tracking_taken(conn, tracking: str, exclude_shipment_id: Optional[str] = None) -> bool:
    if not (tracking or "").strip():
        return False
    t = (tracking or "").strip()
    if exclude_shipment_id:
        row = conn.execute(
            "SELECT 1 FROM shipments WHERE LOWER(TRIM(tracking)) = LOWER(?) AND id != ? LIMIT 1",
            (t, exclude_shipment_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM shipments WHERE LOWER(TRIM(tracking)) = LOWER(?) LIMIT 1",
            (t,),
        ).fetchone()
    return row is not None


@router.post("", response_model=ShipmentResponse, status_code=201)
async def create_shipment(data: ShipmentCreate, _admin=Depends(require_admin)):
    shipment_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    delivery = data.delivery_date.isoformat() if data.delivery_date else None

    client_id = getattr(data, "client_id", None)
    client_phone = getattr(data, "client_phone", None)
    with get_db() as conn:
        if _tracking_taken(conn, data.tracking or ""):
            raise HTTPException(status_code=400, detail="Трекинг-номер уже используется в другой накладной")
        conn.execute(
            """INSERT INTO shipments (
                id, title, tracking, product_list, notes,
                dispatch_date, delivery_date, status, shipping_type,
                weight, amount_to_pay, cashback, file1, file2, file3,
                calculated, created_at, client_id, client_phone
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                shipment_id, data.title, data.tracking, data.product_list, data.notes,
                data.dispatch_date.isoformat(), delivery, data.status.value, data.shipping_type.value,
                data.weight, data.amount_to_pay, data.cashback,
                None, None, None,
                1 if data.calculated else 0, created_at,
                client_id, client_phone,
            ),
        )

    log.info("Создана накладная id=%s tracking=%s", shipment_id, data.tracking or "")
    return _get_shipment_by_id(shipment_id)


@router.post("/{shipment_id}/files", response_model=ShipmentResponse)
async def upload_files(
    shipment_id: str,
    file1: Optional[UploadFile] = File(None),
    file2: Optional[UploadFile] = File(None),
    file3: Optional[UploadFile] = File(None),
    _admin=Depends(require_admin),
):
    _get_shipment_by_id(shipment_id)
    file_paths = _save_files(shipment_id, [file1, file2, file3])
    with get_db() as conn:
        cur = conn.execute("SELECT file1, file2, file3 FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
        f1 = file_paths[0] or cur["file1"]
        f2 = file_paths[1] or cur["file2"]
        f3 = file_paths[2] or cur["file3"]
        conn.execute("UPDATE shipments SET file1=?, file2=?, file3=? WHERE id=?", (f1, f2, f3, shipment_id))
    return _get_shipment_by_id(shipment_id)


@router.put("/{shipment_id}", response_model=ShipmentResponse)
def update_shipment(
    shipment_id: str,
    data: ShipmentUpdate,
    current_user: dict = Depends(get_current_user),
):
    existing = _get_shipment_by_id(shipment_id)
    _check_shipment_access(existing, current_user)

    u = data.model_dump(exclude_unset=True)

    # Клиент может менять только статус
    if current_user["role"] == "client":
        allowed = {"status"}
        u = {k: v for k, v in u.items() if k in allowed}

    title = u.get("title", existing["title"])
    tracking = u.get("tracking", existing["tracking"])
    product_list = u.get("product_list", existing["product_list"])
    notes = u.get("notes", existing["notes"])
    dispatch_date = (u["dispatch_date"].isoformat() if u.get("dispatch_date") else existing["dispatch_date"])
    delivery_date = (u["delivery_date"].isoformat() if u.get("delivery_date") else None) if "delivery_date" in u else existing["delivery_date"]
    status = (u["status"].value if u.get("status") else existing["status"])
    shipping_type = (u["shipping_type"].value if u.get("shipping_type") else existing["shipping_type"])
    weight = u.get("weight", existing["weight"])
    amount_to_pay = u.get("amount_to_pay", existing["amount_to_pay"])
    cashback = u.get("cashback", existing["cashback"])
    calculated = 1 if (u.get("calculated", existing["calculated"])) else 0
    client_id = u.get("client_id") if "client_id" in u else existing.get("client_id")
    client_phone = u.get("client_phone") if "client_phone" in u else existing.get("client_phone")

    with get_db() as conn:
        if _tracking_taken(conn, tracking or "", exclude_shipment_id=shipment_id):
            raise HTTPException(status_code=400, detail="Трекинг-номер уже используется в другой накладной")
        conn.execute(
            """UPDATE shipments SET
                title=?, tracking=?, product_list=?, notes=?,
                dispatch_date=?, delivery_date=?, status=?, shipping_type=?,
                weight=?, amount_to_pay=?, cashback=?, calculated=?,
                client_id=?, client_phone=?
            WHERE id=?""",
            (title, tracking, product_list, notes, dispatch_date, delivery_date, status, shipping_type,
             weight, amount_to_pay, cashback, calculated, client_id, client_phone, shipment_id),
        )
    log.info("Обновлена накладная id=%s by=%s", shipment_id, current_user["username"])
    return _get_shipment_by_id(shipment_id)


@router.post("/{shipment_id}/notify-dispatch")
def notify_dispatch(shipment_id: str, _admin=Depends(require_admin)):
    s = _get_shipment_by_id(shipment_id)
    chat_ids = get_chat_ids_for_shipment(s)
    if not chat_ids:
        raise HTTPException(
            status_code=400,
            detail="У накладной нет клиента с Telegram. Прикрепите клиента, зарегистрированного в боте, или укажите TELEGRAM_CHAT_ID в .env.",
        )
    ok = send_dispatch_notification(s)
    if not ok:
        log.warning("notify_dispatch: не удалось отправить уведомление shipment_id=%s", shipment_id)
        raise HTTPException(status_code=500, detail="Не удалось отправить уведомление")
    with get_db() as conn:
        conn.execute("UPDATE shipments SET dispatch_notified = 1 WHERE id = ?", (shipment_id,))
    log.info("Уведомление об отправке отправлено shipment_id=%s", shipment_id)
    return {"ok": True}


@router.post("/{shipment_id}/notify-delivery")
def notify_delivery(shipment_id: str, _admin=Depends(require_admin)):
    s = _get_shipment_by_id(shipment_id)
    # Ограничение по статусу убрано — уведомление можно отправить в любой момент
    if not s.get("delivery_date"):
        raise HTTPException(status_code=400, detail="Пожалуйста, укажите дату прибытия в накладной")
    chat_ids = get_chat_ids_for_shipment(s)
    if not chat_ids:
        raise HTTPException(
            status_code=400,
            detail="У накладной нет клиента с Telegram. Уведомления можно отправлять только клиентам, зарегистрированным в боте.",
        )
    ok = send_delivery_notification(s)
    if not ok:
        log.warning("notify_delivery: не удалось отправить уведомление shipment_id=%s", shipment_id)
        raise HTTPException(status_code=500, detail="Не удалось отправить уведомление")
    with get_db() as conn:
        conn.execute("UPDATE shipments SET delivery_notified = 1 WHERE id = ?", (shipment_id,))
    log.info("Уведомление о доставке отправлено shipment_id=%s", shipment_id)
    return {"ok": True}


class CalculatedUpdate(BaseModel):
    calculated: bool


@router.patch("/{shipment_id}/calculated", response_model=ShipmentResponse)
def update_calculated(shipment_id: str, data: CalculatedUpdate, _admin=Depends(require_admin)):
    _get_shipment_by_id(shipment_id)
    with get_db() as conn:
        conn.execute("UPDATE shipments SET calculated = ? WHERE id = ?", (1 if data.calculated else 0, shipment_id))
    return _get_shipment_by_id(shipment_id)


@router.delete("/{shipment_id}", status_code=204)
def delete_shipment(shipment_id: str, _admin=Depends(require_admin)):
    _get_shipment_by_id(shipment_id)
    if _s3_available():
        try:
            from backend.services.s3_storage import delete_shipment_files
            delete_shipment_files(shipment_id)
        except Exception:
            pass
    upload_dir = UPLOADS_DIR / shipment_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    with get_db() as conn:
        conn.execute("DELETE FROM shipments WHERE id = ?", (shipment_id,))
    log.info("Накладная удалена id=%s", shipment_id)
    return None


# ---------------------------------------------------------------------------
# Получатели уведомлений для накладной
# ---------------------------------------------------------------------------

@router.get("/{shipment_id}/recipients", response_model=List[RecipientResponse])
def list_recipients(shipment_id: str, _admin=Depends(require_admin)):
    _get_shipment_by_id(shipment_id)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, shipment_id, chat_id, label FROM shipment_recipients WHERE shipment_id = ? ORDER BY label",
            (shipment_id,)
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/{shipment_id}/recipients", response_model=RecipientResponse, status_code=201)
def add_recipient(shipment_id: str, data: RecipientAdd, _admin=Depends(require_admin)):
    _get_shipment_by_id(shipment_id)
    rec_id = str(uuid.uuid4())
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO shipment_recipients (id, shipment_id, chat_id, label) VALUES (?, ?, ?, ?)",
                (rec_id, shipment_id, data.chat_id, data.label or "")
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Этот получатель уже добавлен")
        row = conn.execute(
            "SELECT id, shipment_id, chat_id, label FROM shipment_recipients WHERE id = ?",
            (rec_id,)
        ).fetchone()
    return dict(row)


@router.delete("/{shipment_id}/recipients/{rec_id}", status_code=204)
def remove_recipient(shipment_id: str, rec_id: str, _admin=Depends(require_admin)):
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM shipment_recipients WHERE id = ? AND shipment_id = ?",
            (rec_id, shipment_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Получатель не найден")
        conn.execute("DELETE FROM shipment_recipients WHERE id = ?", (rec_id,))
    return None


@router.get("/{shipment_id}/file/{file_slot}/url")
def get_file_url(
    shipment_id: str,
    file_slot: int,
    current_user: dict = Depends(get_current_user),
):
    """Возвращает URL для скачивания файла (JSON, без редиректа)."""
    if file_slot not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="Недопустимый слот файла")
    s = _get_shipment_by_id(shipment_id)
    _check_shipment_access(s, current_user)
    key = s.get(f"file{file_slot}")
    if not key:
        raise HTTPException(status_code=404, detail="Файл не найден")
    if key.startswith("shipments/") or key.startswith("shipment/"):
        from backend.services.s3_storage import get_presigned_url
        url = get_presigned_url(key)
    else:
        url = key
    return {"url": url}


@router.delete("/{shipment_id}/file/{file_slot}", response_model=ShipmentResponse)
def delete_file(
    shipment_id: str,
    file_slot: int,
    _admin=Depends(require_admin),
):
    """Удаляет файл из слота накладной."""
    if file_slot not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="Недопустимый слот файла")
    s = _get_shipment_by_id(shipment_id)
    key = s.get(f"file{file_slot}")
    if not key:
        raise HTTPException(status_code=404, detail="Файл не найден")
    if _s3_available() and (key.startswith("shipments/") or key.startswith("shipment/")):
        try:
            from backend.services.s3_storage import delete_file_by_key
            delete_file_by_key(key)
        except Exception:
            pass
    with get_db() as conn:
        conn.execute(f"UPDATE shipments SET file{file_slot}=NULL WHERE id=?", (shipment_id,))
    log.info("Удалён файл slot=%s shipment_id=%s", file_slot, shipment_id)
    return _get_shipment_by_id(shipment_id)


@router.get("/{shipment_id}/file/{file_slot}")
def get_file_download(
    shipment_id: str,
    file_slot: int,
    current_user: dict = Depends(get_current_user),
):
    """Редирект на скачивание файла (оставлен для обратной совместимости)."""
    if file_slot not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="Недопустимый слот файла")
    s = _get_shipment_by_id(shipment_id)
    _check_shipment_access(s, current_user)
    key = s.get(f"file{file_slot}")
    if not key:
        raise HTTPException(status_code=404, detail="Файл не найден")
    if key.startswith("shipments/") or key.startswith("shipment/"):
        from backend.services.s3_storage import get_presigned_url
        url = get_presigned_url(key)
        return RedirectResponse(url=url, status_code=302)
    return RedirectResponse(url=key, status_code=302)
