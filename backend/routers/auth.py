import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Depends

from backend.auth import (
    verify_password,
    create_access_token,
    get_current_user,
)
from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import LoginRequest, UserResponse, BotLoginRequest, BotLogoutRequest

router = APIRouter(tags=["auth"])
log = get_logger("auth")


# ---------------------------------------------------------------------------
# Web auth
# ---------------------------------------------------------------------------

@router.post("/api/auth/login")
def login(data: LoginRequest):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (data.username,)
        ).fetchone()
    if not row or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )
    token = create_access_token({
        "sub": row["id"],
        "username": row["username"],
        "role": row["role"],
        "client_id": row["client_id"],
    })
    log.info("Вход: username=%s role=%s", row["username"], row["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": row["role"],
        "client_id": row["client_id"],
        "username": row["username"],
        "id": row["id"],
    }


@router.get("/api/auth/me", response_model=UserResponse)
def me(current_user: dict = Depends(get_current_user)):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (current_user["id"],)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "client_id": row["client_id"],
        "created_at": row["created_at"],
    }


# ---------------------------------------------------------------------------
# Bot session management
# ---------------------------------------------------------------------------

@router.post("/api/bot/login")
def bot_login(data: BotLoginRequest):
    """Бот создаёт сессию для telegram_chat_id после проверки логина/пароля."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (data.username,)
        ).fetchone()
        if not row or not verify_password(data.password, row["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный логин или пароль",
            )
        # Создаём или обновляем сессию для этого telegram_chat_id
        created_at = datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO bot_sessions (telegram_chat_id, user_id, client_id, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(telegram_chat_id) DO UPDATE SET
                   user_id = excluded.user_id,
                   client_id = excluded.client_id,
                   created_at = excluded.created_at""",
            (data.telegram_chat_id, row["id"], row["client_id"], created_at),
        )
    log.info("Bot login: telegram_chat_id=%s username=%s", data.telegram_chat_id, data.username)
    return {
        "ok": True,
        "role": row["role"],
        "client_id": row["client_id"],
        "username": row["username"],
    }


@router.post("/api/bot/logout")
def bot_logout(data: BotLogoutRequest):
    """Удаляет бот-сессию для telegram_chat_id."""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM bot_sessions WHERE telegram_chat_id = ?",
            (data.telegram_chat_id,),
        )
    log.info("Bot logout: telegram_chat_id=%s", data.telegram_chat_id)
    return {"ok": True}


@router.get("/api/bot/me/{telegram_chat_id}")
def bot_me(telegram_chat_id: str):
    """Возвращает данные сессии для telegram_chat_id (для бота)."""
    with get_db() as conn:
        row = conn.execute(
            """SELECT bs.*, u.username, u.role
               FROM bot_sessions bs
               JOIN users u ON bs.user_id = u.id
               WHERE bs.telegram_chat_id = ?""",
            (telegram_chat_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    return {
        "client_id": row["client_id"],
        "username": row["username"],
        "role": row["role"],
        "user_id": row["user_id"],
    }
