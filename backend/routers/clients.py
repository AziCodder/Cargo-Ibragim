import os
import uuid
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.auth import hash_password, require_admin
from backend.database import get_db, row_to_client
from backend.logging_config import get_logger
from backend.models import ClientCreate, ClientUpdate, ClientResponse, ApproveClientRequest

router = APIRouter(prefix="/api/clients", tags=["clients"])
log = get_logger("clients")


def _get_client(client_id: str) -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Клиент не найден")
        return row_to_client(row)


@router.get("", response_model=list)
def list_clients(_admin=Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM clients WHERE status = 'approved' OR status IS NULL ORDER BY full_name ASC"
        ).fetchall()
    return [row_to_client(r) for r in rows]


@router.get("/pending", response_model=list)
def list_pending_clients(_admin=Depends(require_admin)):
    """Список клиентов, ожидающих одобрения (зарегистрировались через бот)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM clients WHERE status = 'pending' ORDER BY created_at DESC"
        ).fetchall()
    return [row_to_client(r) for r in rows]


class ClientRegister(BaseModel):
    full_name: str
    city: str
    telegram_chat_id: str


@router.post("/register", response_model=ClientResponse, status_code=201)
def register_client(data: ClientRegister):
    """Регистрация клиента из бота — сохраняется как pending (ожидает одобрения)."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id, status FROM clients WHERE telegram_chat_id = ?",
            (data.telegram_chat_id,),
        ).fetchone()
        if existing:
            return _get_client(existing["id"])
        client_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO clients (id, full_name, city, telegram_chat_id, phone, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (client_id, data.full_name, data.city, data.telegram_chat_id, None, "pending", created_at),
        )
    log.info("Новая заявка на регистрацию: id=%s telegram_chat_id=%s name=%s", client_id, data.telegram_chat_id, data.full_name)

    # Уведомляем администратора в Telegram
    _notify_admin_new_registration(data.full_name, data.city, data.telegram_chat_id)

    return _get_client(client_id)


def _notify_admin_new_registration(full_name: str, city: str, telegram_chat_id: str):
    """Отправляет сообщение администратору о новой заявке."""
    admin_chat_id = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not admin_chat_id or not bot_token:
        return
    try:
        text = (
            f"🆕 <b>Новая заявка на регистрацию!</b>\n\n"
            f"👤 ФИО: {full_name}\n"
            f"🏙 Город: {city}\n"
            f"💬 Telegram ID: <code>{telegram_chat_id}</code>\n\n"
            f"Откройте раздел <b>Клиенты → Заявки</b> на сайте чтобы одобрить."
        )
        httpx.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": admin_chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10.0,
        )
    except Exception as e:
        log.warning("Не удалось уведомить администратора о новой заявке: %s", e)


@router.post("/{client_id}/approve", response_model=ClientResponse)
def approve_client(client_id: str, data: ApproveClientRequest, _admin=Depends(require_admin)):
    """Одобрить заявку клиента: создать аккаунт и уведомить его в Telegram."""
    client = _get_client(client_id)
    telegram_chat_id = client.get("telegram_chat_id")

    if not telegram_chat_id:
        raise HTTPException(status_code=400, detail="У клиента нет Telegram chat_id")

    with get_db() as conn:
        # Проверяем что логин не занят
        existing_user = conn.execute(
            "SELECT id FROM users WHERE username = ?", (data.username,)
        ).fetchone()
        if existing_user:
            raise HTTPException(status_code=400, detail="Логин уже занят, выберите другой")

        # Создаём пользователя
        user_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, client_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, data.username, hash_password(data.password), "client", client_id, created_at),
        )

        # Обновляем статус клиента на approved
        conn.execute("UPDATE clients SET status = 'approved' WHERE id = ?", (client_id,))

        # Создаём bot_session — пользователь автоматически залогинен в боте
        conn.execute(
            """INSERT INTO bot_sessions (telegram_chat_id, user_id, client_id, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(telegram_chat_id) DO UPDATE SET
                   user_id = excluded.user_id,
                   client_id = excluded.client_id,
                   created_at = excluded.created_at""",
            (telegram_chat_id, user_id, client_id, created_at),
        )

    log.info("Клиент одобрен: id=%s username=%s telegram_chat_id=%s", client_id, data.username, telegram_chat_id)

    # Отправляем данные для входа в Telegram
    _send_credentials_to_client(telegram_chat_id, data.username, data.password)

    return _get_client(client_id)


def _send_credentials_to_client(telegram_chat_id: str, username: str, password: str):
    """Отправляет клиенту логин и пароль через Telegram Bot API."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        return
    try:
        text = (
            f"✅ <b>Ваша регистрация одобрена!</b>\n\n"
            f"Данные для входа на сайт:\n"
            f"🔑 Логин: <code>{username}</code>\n"
            f"🔒 Пароль: <code>{password}</code>\n\n"
            f"В боте вы уже авторизованы автоматически.\n"
            f"Нажмите <b>«Товар в дороге»</b> чтобы посмотреть ваши заказы.\n\n"
            f"Сохраните эти данные — они нужны для входа на сайт."
        )
        httpx.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": telegram_chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10.0,
        )
    except Exception as e:
        log.warning("Не удалось отправить данные клиенту telegram_chat_id=%s: %s", telegram_chat_id, e)


@router.get("/by-telegram/{telegram_chat_id}", response_model=ClientResponse)
def get_client_by_telegram(telegram_chat_id: str):
    """Проверка: зарегистрирован ли пользователь по telegram_chat_id (для бота, публичный)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE telegram_chat_id = ?",
            (telegram_chat_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Клиент не найден")
        return row_to_client(row)


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: str, _admin=Depends(require_admin)):
    return _get_client(client_id)


@router.post("", response_model=ClientResponse, status_code=201)
def create_client(data: ClientCreate, _admin=Depends(require_admin)):
    client_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO clients (id, full_name, city, telegram_chat_id, phone, group_chat_id, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                client_id,
                data.full_name,
                data.city,
                data.telegram_chat_id,
                data.phone,
                data.group_chat_id,
                "approved",
                created_at,
            ),
        )
    return _get_client(client_id)


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(client_id: str, data: ClientUpdate, _admin=Depends(require_admin)):
    _get_client(client_id)
    u = data.model_dump(exclude_unset=True)
    with get_db() as conn:
        cur = conn.execute("SELECT full_name, city, phone, group_chat_id FROM clients WHERE id = ?", (client_id,)).fetchone()
        full_name = u.get("full_name", cur["full_name"])
        city = u.get("city", cur["city"])
        phone = u.get("phone", cur["phone"]) if "phone" in u else cur["phone"]
        group_chat_id = u.get("group_chat_id", cur["group_chat_id"]) if "group_chat_id" in u else cur["group_chat_id"]
        conn.execute(
            "UPDATE clients SET full_name=?, city=?, phone=?, group_chat_id=? WHERE id=?",
            (full_name, city, phone, group_chat_id, client_id),
        )
    return _get_client(client_id)


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: str, _admin=Depends(require_admin)):
    _get_client(client_id)
    with get_db() as conn:
        conn.execute("UPDATE shipments SET client_id = NULL WHERE client_id = ?", (client_id,))
        conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    return None
