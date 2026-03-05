import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import get_db, row_to_client
from backend.models import ClientCreate, ClientUpdate, ClientResponse

router = APIRouter(prefix="/api/clients", tags=["clients"])


def _get_client(client_id: str) -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Клиент не найден")
        return row_to_client(row)


@router.get("", response_model=list)
def list_clients():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM clients ORDER BY full_name ASC"
        ).fetchall()
    return [row_to_client(r) for r in rows]


class ClientRegister(BaseModel):
    full_name: str
    city: str
    telegram_chat_id: str


@router.post("/register", response_model=ClientResponse, status_code=201)
def register_client(data: ClientRegister):
    """Регистрация клиента из бота (вызывается ботом)."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM clients WHERE telegram_chat_id = ?",
            (data.telegram_chat_id,),
        ).fetchone()
        if existing:
            return _get_client(existing["id"])
        client_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO clients (id, full_name, city, telegram_chat_id, phone, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (client_id, data.full_name, data.city, data.telegram_chat_id, None, created_at),
        )
    return _get_client(client_id)


@router.get("/by-telegram/{telegram_chat_id}", response_model=ClientResponse)
def get_client_by_telegram(telegram_chat_id: str):
    """Проверка: зарегистрирован ли пользователь по telegram_chat_id (для бота)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE telegram_chat_id = ?",
            (telegram_chat_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Клиент не найден")
        return row_to_client(row)


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: str):
    return _get_client(client_id)


@router.post("", response_model=ClientResponse, status_code=201)
def create_client(data: ClientCreate):
    client_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO clients (id, full_name, city, telegram_chat_id, phone, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                client_id,
                data.full_name,
                data.city,
                data.telegram_chat_id,
                data.phone,
                created_at,
            ),
        )
    return _get_client(client_id)


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(client_id: str, data: ClientUpdate):
    _get_client(client_id)
    u = data.model_dump(exclude_unset=True)
    with get_db() as conn:
        cur = conn.execute("SELECT full_name, city, phone FROM clients WHERE id = ?", (client_id,)).fetchone()
        full_name = u.get("full_name", cur["full_name"])
        city = u.get("city", cur["city"])
        phone = u.get("phone", cur["phone"]) if "phone" in u else cur["phone"]
        conn.execute(
            "UPDATE clients SET full_name=?, city=?, phone=? WHERE id=?",
            (full_name, city, phone, client_id),
        )
    return _get_client(client_id)


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: str):
    _get_client(client_id)
    with get_db() as conn:
        conn.execute("UPDATE shipments SET client_id = NULL WHERE client_id = ?", (client_id,))
        conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    return None


