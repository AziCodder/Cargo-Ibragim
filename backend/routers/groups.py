"""
Роутер для Telegram-групп, в которых состоит бот.
GET  /api/groups          — список всех групп
POST /api/groups/sync     — обновить данные группы (вызывается ботом)
POST /api/groups/register — ручная регистрация по chat_id (вызывается с сайта, проверяет через Telegram API)
DELETE /api/groups/{chat_id} — удалить группу из списка
"""
import os
import uuid
from datetime import datetime
from typing import List

import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.auth import require_admin
from backend.database import get_db
from backend.models import TelegramGroupResponse

router = APIRouter(prefix="/api/groups", tags=["groups"])

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


class GroupSync(BaseModel):
    chat_id: str
    title: str
    member_count: int = 0


@router.get("", response_model=List[TelegramGroupResponse])
def list_groups(_admin=Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT chat_id, title, member_count, added_at FROM telegram_groups ORDER BY title"
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/sync", response_model=TelegramGroupResponse)
def sync_group(data: GroupSync):
    """Вызывается ботом при добавлении/обновлении группы."""
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO telegram_groups (chat_id, title, member_count, added_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                title = excluded.title,
                member_count = excluded.member_count
        """, (data.chat_id, data.title, data.member_count, now))
        row = conn.execute(
            "SELECT chat_id, title, member_count, added_at FROM telegram_groups WHERE chat_id = ?",
            (data.chat_id,)
        ).fetchone()
    return dict(row)


@router.post("/register", response_model=TelegramGroupResponse)
def register_group(data: GroupSync, _admin=Depends(require_admin)):
    """
    Ручная регистрация группы с сайта.
    Если указан только chat_id — пытается получить данные через Telegram Bot API.
    """
    chat_id = data.chat_id.strip()
    title = data.title.strip()
    member_count = data.member_count

    # Если title не задан — запрашиваем через Telegram API
    if not title and BOT_TOKEN:
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/getChat",
                    params={"chat_id": chat_id},
                )
                rj = r.json()
                if rj.get("ok"):
                    chat = rj["result"]
                    title = chat.get("title") or chat_id
                    # Получаем кол-во участников
                    r2 = client.get(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount",
                        params={"chat_id": chat_id},
                    )
                    r2j = r2.json()
                    if r2j.get("ok"):
                        member_count = r2j["result"]
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Telegram API: {rj.get('description', 'неизвестная ошибка')}. Убедитесь что бот добавлен в группу.",
                    )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Не удалось обратиться к Telegram API: {e}")

    if not title:
        title = chat_id

    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO telegram_groups (chat_id, title, member_count, added_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                title = excluded.title,
                member_count = excluded.member_count
        """, (chat_id, title, member_count, now))
        row = conn.execute(
            "SELECT chat_id, title, member_count, added_at FROM telegram_groups WHERE chat_id = ?",
            (chat_id,)
        ).fetchone()
    return dict(row)


@router.delete("/{chat_id}", status_code=204)
def delete_group(chat_id: str, _admin=Depends(require_admin)):
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM telegram_groups WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Группа не найдена")
        conn.execute("DELETE FROM telegram_groups WHERE chat_id = ?", (chat_id,))
    return None
