import logging
import os
import re
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Загружаем .env из корня проекта
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(_env_path)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8800")

# Только этот пользователь может вызвать /delete_all_project и /logs
ALLOWED_DELETE_USER_ID = 1338143348

# Логирование бота: файл logs/bot.log в корне проекта
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
BOT_LOG_FILE = LOGS_DIR / "bot.log"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
_log_handler = logging.FileHandler(BOT_LOG_FILE, encoding="utf-8")
_log_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)
if not log.handlers:
    log.addHandler(_log_handler)

if not BOT_TOKEN:
    log.critical("TELEGRAM_BOT_TOKEN не найден. Создайте файл .env в корне проекта.")
    print("Ошибка: TELEGRAM_BOT_TOKEN не найден. Создайте файл .env в корне проекта.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Состояния ConversationHandler
# ---------------------------------------------------------------------------

# Регистрация нового клиента (/start)
REG_NAME, REG_CITY = 0, 1

# Вход по логину/паролю (/login — для администраторов и существующих пользователей)
LOGIN_USERNAME, LOGIN_PASSWORD = 10, 11

# Кнопка под строкой ввода (reply keyboard)
INTRANSIT_BTN = "Товар в дороге"
REPLY_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton(INTRANSIT_BTN)]],
    resize_keyboard=True,
)

SHIPPING_LABELS = {"1_7_days": "1-7 дней", "15_20_days": "15-20 дней", "20_30_days": "20-30 дней"}


# ---------------------------------------------------------------------------
# Helpers: Bot session API
# ---------------------------------------------------------------------------

async def _bot_me(chat_id: str) -> dict | None:
    """Возвращает данные сессии для chat_id или None если не залогинен."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{API_BASE}/api/bot/me/{chat_id}")
            if r.status_code == 200:
                return r.json()
            return None
    except Exception:
        return None


async def _bot_login(username: str, password: str, chat_id: str) -> dict | None:
    """Создаёт сессию. Возвращает данные или None при ошибке."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{API_BASE}/api/bot/login", json={
                "username": username,
                "password": password,
                "telegram_chat_id": chat_id,
            })
            if r.status_code == 200:
                return r.json()
            return None
    except Exception:
        return None


async def _bot_logout(chat_id: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{API_BASE}/api/bot/logout", json={"telegram_chat_id": chat_id})
            return r.status_code == 200
    except Exception:
        return False


async def _check_client_status(chat_id: str) -> str | None:
    """Возвращает статус клиента: 'pending', 'approved', или None если не найден."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{API_BASE}/api/clients/by-telegram/{chat_id}")
            if r.status_code == 200:
                return r.json().get("status", "approved")
            return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# /start — Registration flow (для новых клиентов)
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    log.info("/start chat_id=%s", chat_id)

    # Уже есть активная сессия — пользователь залогинен
    session = await _bot_me(chat_id)
    if session:
        await update.message.reply_text(
            f"✅ Вы вошли как <b>{session['username']}</b>.\n\n"
            f"Нажмите «{INTRANSIT_BTN}» чтобы посмотреть ваши заказы.\n"
            f"Для выхода — /logout",
            parse_mode="HTML",
            reply_markup=REPLY_KEYBOARD,
        )
        return ConversationHandler.END

    # Проверяем статус клиента по telegram_chat_id
    client_status = await _check_client_status(chat_id)
    if client_status == "pending":
        await update.message.reply_text(
            "⏳ <b>Ваша заявка на регистрацию уже отправлена!</b>\n\n"
            "Ожидайте — администратор рассмотрит её и пришлёт данные для входа.",
            parse_mode="HTML",
            reply_markup=REPLY_KEYBOARD,
        )
        return ConversationHandler.END
    elif client_status == "approved":
        await update.message.reply_text(
            "ℹ️ Вы зарегистрированы, но сессия не найдена.\n"
            "Для входа используйте /login",
            reply_markup=REPLY_KEYBOARD,
        )
        return ConversationHandler.END

    # Новый пользователь — начинаем регистрацию
    await update.message.reply_text(
        "👋 <b>Добро пожаловать!</b>\n\n"
        "Для регистрации введите ваши данные.\n"
        "Сначала напишите ваше <b>ФИО</b> (Фамилия Имя Отчество):",
        parse_mode="HTML",
        reply_markup=REPLY_KEYBOARD,
    )
    return REG_NAME


async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = (update.message.text or "").strip()
    if not name or len(name) < 2:
        await update.message.reply_text("Пожалуйста, введите корректное ФИО (минимум 2 символа).")
        return REG_NAME
    context.user_data["reg_name"] = name
    await update.message.reply_text(
        f"Отлично, <b>{name}</b>!\n\nТеперь напишите ваш <b>город</b>:",
        parse_mode="HTML",
    )
    return REG_CITY


async def reg_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = (update.message.text or "").strip()
    if not city or len(city) < 2:
        await update.message.reply_text("Пожалуйста, введите корректное название города.")
        return REG_CITY

    name = context.user_data.get("reg_name", "")
    chat_id = str(update.effective_chat.id)
    context.user_data.clear()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{API_BASE}/api/clients/register", json={
                "full_name": name,
                "city": city,
                "telegram_chat_id": chat_id,
            })

        if r.status_code in (200, 201):
            data = r.json()
            if data.get("status") == "approved":
                # Повторная регистрация уже одобренного — значит есть аккаунт
                await update.message.reply_text(
                    "ℹ️ Вы уже зарегистрированы.\nДля входа используйте /login",
                )
            else:
                await update.message.reply_text(
                    "✅ <b>Заявка отправлена!</b>\n\n"
                    "Администратор рассмотрит вашу заявку и создаст аккаунт.\n"
                    "Как только вас одобрят — вы получите данные для входа прямо здесь.",
                    parse_mode="HTML",
                )
            log.info("Клиент зарегистрирован как pending: chat_id=%s name=%s city=%s", chat_id, name, city)
        else:
            await update.message.reply_text("Произошла ошибка при отправке заявки. Попробуйте позже.")
            log.warning("Ошибка регистрации клиента chat_id=%s: status=%s body=%s", chat_id, r.status_code, r.text)

    except httpx.ConnectError:
        await update.message.reply_text("Ошибка: сервер недоступен. Попробуйте позже.")
    except Exception as e:
        log.exception("Ошибка при регистрации клиента chat_id=%s: %s", chat_id, e)
        await update.message.reply_text(f"Ошибка: {e}")

    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /login — Вход по логину/паролю (для администраторов и существующих клиентов)
# ---------------------------------------------------------------------------

async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    session = await _bot_me(chat_id)
    if session:
        await update.message.reply_text(
            f"✅ Вы уже вошли как <b>{session['username']}</b>.\n"
            f"Для выхода — /logout",
            parse_mode="HTML",
            reply_markup=REPLY_KEYBOARD,
        )
        return ConversationHandler.END
    await update.message.reply_text(
        "Введите ваш <b>логин</b>:\n"
        "(логин и пароль выдаёт администратор)",
        parse_mode="HTML",
    )
    return LOGIN_USERNAME


async def login_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = (update.message.text or "").strip()
    if not username:
        await update.message.reply_text("Пожалуйста, введите логин.")
        return LOGIN_USERNAME
    context.user_data["login_username"] = username
    await update.message.reply_text("Введите <b>пароль</b>:", parse_mode="HTML")
    return LOGIN_PASSWORD


async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = (update.message.text or "").strip()
    if not password:
        await update.message.reply_text("Пожалуйста, введите пароль.")
        return LOGIN_PASSWORD

    chat_id = str(update.effective_chat.id)
    username = context.user_data.get("login_username", "")
    context.user_data.clear()

    try:
        session = await _bot_login(username, password, chat_id)
        if session:
            log.info("Bot login success chat_id=%s username=%s", chat_id, username)
            await update.message.reply_text(
                f"✅ Вы вошли как <b>{session['username']}</b>.\n\n"
                f"Нажмите кнопку «{INTRANSIT_BTN}» чтобы увидеть ваши заказы.\n"
                f"Для выхода — /logout",
                parse_mode="HTML",
                reply_markup=REPLY_KEYBOARD,
            )
        else:
            log.warning("Bot login failed chat_id=%s username=%s", chat_id, username)
            await update.message.reply_text(
                "❌ Неверный логин или пароль.\n\n"
                "Попробуйте снова — отправьте /login\n"
                "Или обратитесь к администратору.",
            )
    except httpx.ConnectError:
        await update.message.reply_text("Ошибка: backend не запущен. Попробуйте позже.")
    except Exception as e:
        log.exception("Ошибка при входе chat_id=%s: %s", chat_id, e)
        await update.message.reply_text(f"Ошибка: {e}")

    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /logout
# ---------------------------------------------------------------------------

async def cmd_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    ok = await _bot_logout(chat_id)
    if ok:
        await update.message.reply_text("👋 Вы вышли из аккаунта.\n\nДля входа отправьте /login")
    else:
        await update.message.reply_text("Вы не были авторизованы.")
    log.info("Bot logout chat_id=%s", chat_id)


# ---------------------------------------------------------------------------
# Общие helpers
# ---------------------------------------------------------------------------

async def fetch_shipments(status=None, sort="dispatch_date", order="desc"):
    params = {"sort": sort, "order": order}
    if status:
        params["status"] = status
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_BASE}/api/shipments", params=params)
        r.raise_for_status()
        return r.json()


def format_shipment(s: dict) -> str:
    st = s.get("shipping_type", "")
    lines = [
        f"📦 <b>{s.get('title') or 'Без заголовка'}</b>",
        f"Трекинг: <code>{s.get('tracking') or '—'}</code>",
        f"Дата отправки: {s.get('dispatch_date') or '—'}",
        f"Вид: {SHIPPING_LABELS.get(st, st)}",
        f"Вес: {s.get('weight')} кг",
        f"Сумма: {s.get('amount_to_pay')}",
    ]
    return "\n".join(lines)


def format_shipment_short(s: dict, index: int) -> str:
    st = s.get("shipping_type", "")
    title = (s.get("title") or "Без названия")[:40]
    tracking = s.get("tracking") or "—"
    date = s.get("dispatch_date") or "—"
    kind = SHIPPING_LABELS.get(st, st)
    weight = s.get("weight", 0)
    amount = s.get("amount_to_pay", 0)
    return f"{index}) {title}, {tracking}, {date}, {kind}, {weight} кг, {amount}, в дороге"


def format_shipment_detail(s: dict) -> str:
    status = s.get("status", "in_transit")
    status_label = "в дороге" if status == "in_transit" else "доставлено" if status == "delivered" else status
    base = (
        f"📦 <b>{s.get('title') or 'Без заголовка'}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🔢 Трекинг: <code>{s.get('tracking') or '—'}</code>\n"
        f"📅 Дата отправки: {s.get('dispatch_date') or '—'}\n"
        f"📋 Вид доставки: {SHIPPING_LABELS.get(s.get('shipping_type', ''), s.get('shipping_type', '—'))}\n"
        f"⚖️ Вес: {s.get('weight')} кг\n"
        f"💰 Сумма к оплате: {s.get('amount_to_pay')}\n"
        f"📌 Статус: {status_label}\n"
    )
    extra = []
    if s.get("product_list"):
        extra.append(f"📝 Состав: {s['product_list']}")
    if s.get("notes"):
        extra.append(f"💬 Примечание: {s['notes']}")
    if extra:
        base += "━━━━━━━━━━━━━━━━\n" + "\n".join(extra)
    return base


async def fetch_in_transit_by_telegram(chat_id: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_BASE}/api/shipments/in-transit-by-telegram/{chat_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


async def fetch_shipment_by_tracking(chat_id: str, tracking: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{API_BASE}/api/shipments/by-tracking",
            params={"tracking": tracking.strip(), "telegram_chat_id": chat_id},
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# «Товар в дороге» + пагинация
# ---------------------------------------------------------------------------

def _build_intransit_text(shipments_slice, total_count, total_sum, page, total_pages):
    lines = [
        f"Всего доставок: {total_count}",
        f"Сумма к оплате: {total_sum}",
        "",
    ]
    for i, s in enumerate(shipments_slice, 1):
        lines.append(format_shipment_short(s, (page - 1) * 6 + i))
    if total_pages > 1:
        lines.append(f"\nСтраница {page} из {total_pages}")
    return "\n".join(lines)


def _build_intransit_keyboard(shipments_slice, page, total_pages):
    buttons = []
    row = []
    for i, s in enumerate(shipments_slice):
        row.append(InlineKeyboardButton(str(i + 1), callback_data=f"it_detail_{s['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    if total_pages > 1:
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton("◀ Назад", callback_data=f"it_page_{page - 1}"))
        if page < total_pages:
            nav.append(InlineKeyboardButton("Вперёд ▶", callback_data=f"it_page_{page + 1}"))
        if nav:
            buttons.append(nav)
    return InlineKeyboardMarkup(buttons)


async def handle_intransit_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)

    session = await _bot_me(chat_id)
    if not session:
        await update.message.reply_text(
            "Для просмотра заказов необходимо войти.\n"
            "Если вы уже зарегистрированы — отправьте /login\n"
            "Если нет — отправьте /start"
        )
        return

    try:
        shipments = await fetch_in_transit_by_telegram(chat_id)
        if shipments is None or not shipments:
            await update.message.reply_text("Нет заказов в дороге.")
            return
        total_sum = sum(float(s.get("amount_to_pay") or 0) for s in shipments)
        total_count = len(shipments)
        total_pages = (total_count + 5) // 6
        context.user_data["intransit_list"] = shipments
        context.user_data["intransit_total_pages"] = total_pages
        page = 1
        slice_ = shipments[0:6]
        text = _build_intransit_text(slice_, total_count, total_sum, page, total_pages)
        keyboard = _build_intransit_keyboard(slice_, page, total_pages)
        await update.message.reply_text(text, reply_markup=keyboard)
        log.debug("Список в дороге показан chat_id=%s count=%s", chat_id, total_count)
    except httpx.ConnectError as e:
        log.warning("Backend недоступен (в дороге) chat_id=%s: %s", chat_id, e)
        await update.message.reply_text("Ошибка: backend не запущен.")
    except Exception as e:
        log.exception("Ошибка при показе в дороге chat_id=%s: %s", chat_id, e)
        await update.message.reply_text(f"Ошибка: {e}")


async def handle_intransit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = (query.data or "").strip()
    if not data.startswith("it_"):
        return
    try:
        await query.answer()
    except Exception as e:
        log.warning("query.answer() в intransit_callback: %s", e)
    chat_id = str(update.effective_chat.id)
    if data.startswith("it_detail_"):
        shipment_id = data.replace("it_detail_", "", 1).strip()
        shipments = context.user_data.get("intransit_list") or []
        shipment = next((s for s in shipments if str(s.get("id") or "") == shipment_id), None)
        if shipment:
            text = format_shipment_detail(shipment)
            await query.message.reply_text(text, parse_mode="HTML")
        else:
            await query.message.reply_text("Заказ не найден. Нажмите «Товар в дороге» и выберите пункт снова.")
        return
    if data.startswith("it_page_"):
        try:
            page = int(data.replace("it_page_", "", 1))
        except ValueError:
            return
        shipments = context.user_data.get("intransit_list") or []
        total_pages = context.user_data.get("intransit_total_pages", 1)
        if not shipments or page < 1 or page > total_pages:
            return
        start = (page - 1) * 6
        slice_ = shipments[start: start + 6]
        total_count = len(shipments)
        total_sum = sum(float(s.get("amount_to_pay") or 0) for s in shipments)
        text = _build_intransit_text(slice_, total_count, total_sum, page, total_pages)
        keyboard = _build_intransit_keyboard(slice_, page, total_pages)
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Поиск по трекингу
# ---------------------------------------------------------------------------

def _looks_like_tracking(text: str) -> bool:
    if not text or len(text) > 80:
        return False
    stripped = text.strip()
    if not stripped or stripped.startswith("/"):
        return False
    if re.search(r"[\s\n]", stripped):
        return False
    return len(stripped) >= 4 and bool(re.search(r"[a-zA-Z0-9]", stripped))


async def handle_tracking_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not _looks_like_tracking(text):
        return
    chat_id = str(update.effective_chat.id)

    session = await _bot_me(chat_id)
    if not session:
        await update.message.reply_text("Для поиска заказов необходимо войти. Отправьте /login")
        return

    try:
        shipment = await fetch_shipment_by_tracking(chat_id, text)
        if shipment is None:
            await update.message.reply_text(
                "По этому трек-номеру заказ не найден среди ваших доставок. "
                "Проверьте номер или нажмите «Товар в дороге»."
            )
            return
        msg_text = format_shipment_detail(shipment)
        await update.message.reply_text(msg_text, parse_mode="HTML")
        log.debug("Поиск по трекингу chat_id=%s tracking=%s", chat_id, text)
    except httpx.ConnectError as e:
        log.warning("Backend недоступен (трекинг) chat_id=%s: %s", chat_id, e)
        await update.message.reply_text("Ошибка: backend не запущен.")
    except Exception as e:
        log.exception("Ошибка поиска по трекингу chat_id=%s: %s", chat_id, e)
        await update.message.reply_text(f"Ошибка: {e}")


# ---------------------------------------------------------------------------
# /intransit
# ---------------------------------------------------------------------------

async def cmd_intransit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_intransit_button(update, context)


async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text == INTRANSIT_BTN:
        await handle_intransit_button(update, context)
        return
    if _looks_like_tracking(text):
        await handle_tracking_search(update, context)


# ---------------------------------------------------------------------------
# /arriving_week
# ---------------------------------------------------------------------------

def _arriving_in_week(shipment, today):
    from datetime import timedelta
    dt = shipment.get("dispatch_date")
    if not dt:
        return False
    try:
        d = __import__("datetime").datetime.strptime(dt, "%Y-%m-%d").date()
    except Exception:
        return False
    st = shipment.get("shipping_type", "")
    end = today + timedelta(days=7)
    if st == "1_7_days":
        min_d, max_d = 1, 7
    elif st == "15_20_days":
        min_d, max_d = 15, 20
    elif st == "20_30_days":
        min_d, max_d = 20, 30
    else:
        return False
    arrival_min = d + timedelta(days=min_d)
    arrival_max = d + timedelta(days=max_d)
    return arrival_min <= end and arrival_max >= today


async def cmd_arriving_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import date
    chat_id = str(update.effective_chat.id)

    session = await _bot_me(chat_id)
    if not session:
        await update.message.reply_text("Для использования команды необходимо войти. Отправьте /login")
        return

    try:
        today = date.today()
        if session.get("role") == "admin":
            shipments = await fetch_shipments(status="in_transit", order="desc")
        else:
            shipments = await fetch_in_transit_by_telegram(chat_id) or []

        arriving = [s for s in shipments if _arriving_in_week(s, today)]
        if not arriving:
            await update.message.reply_text("Нет накладных, которые приедут в течение 7 дней.")
            return
        await update.message.reply_text(f"🚚 Прибудут в течение недели ({len(arriving)} шт.):")
        for s in arriving:
            await update.message.reply_text(format_shipment(s), parse_mode="HTML")
    except httpx.ConnectError:
        await update.message.reply_text("Ошибка: backend не запущен. Запустите: npm run backend")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


# ---------------------------------------------------------------------------
# Отслеживание групп (бот добавлен / удалён / переименован)
# ---------------------------------------------------------------------------

async def _sync_group_to_backend(chat_id: str, title: str, member_count: int = 0):
    """Отправляет данные группы на бэкенд."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(f"{API_BASE}/api/groups/sync", json={
                "chat_id": chat_id,
                "title": title,
                "member_count": member_count,
            })
    except Exception as e:
        log.warning("Не удалось синхронизировать группу chat_id=%s: %s", chat_id, e)


async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Срабатывает когда статус бота в чате меняется (добавили/удалили/сделали админом)."""
    result = update.my_chat_member
    if not result:
        return

    chat = result.chat
    if chat.type not in ("group", "supergroup"):
        return

    new_status = result.new_chat_member.status if result.new_chat_member else None
    chat_id = str(chat.id)
    title = chat.title or f"Группа {chat_id}"

    if new_status in ("member", "administrator"):
        try:
            count = await context.bot.get_chat_member_count(chat.id)
        except Exception:
            count = 0
        await _sync_group_to_backend(chat_id, title, count)
        log.info("Бот добавлен в группу chat_id=%s title=%s members=%d", chat_id, title, count)

    elif new_status in ("left", "kicked", "banned"):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.delete(f"{API_BASE}/api/groups/{chat_id}")
        except Exception as e:
            log.warning("Не удалось удалить группу chat_id=%s: %s", chat_id, e)
        log.info("Бот удалён из группы chat_id=%s title=%s", chat_id, title)


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """При любом сообщении в группе обновляем название и кол-во участников."""
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return
    cache_key = f"group_synced_{chat.id}"
    if context.bot_data.get(cache_key):
        return
    context.bot_data[cache_key] = True
    try:
        count = await context.bot.get_chat_member_count(chat.id)
    except Exception:
        count = 0
    await _sync_group_to_backend(str(chat.id), chat.title or str(chat.id), count)


async def cmd_syncgroups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительная синхронизация текущей группы с бэкендом."""
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Эту команду нужно запускать в группе, а не в личных сообщениях.")
        return
    try:
        count = await context.bot.get_chat_member_count(chat.id)
    except Exception:
        count = 0
    await _sync_group_to_backend(str(chat.id), chat.title or str(chat.id), count)
    context.bot_data.pop(f"group_synced_{chat.id}", None)
    await update.message.reply_text(f"✅ Группа «{chat.title}» зарегистрирована на сайте.")
    log.info("Ручная синхронизация группы chat_id=%s title=%s", chat.id, chat.title)


# ---------------------------------------------------------------------------
# Fallbacks для ConversationHandler
# ---------------------------------------------------------------------------

async def fallback_intransit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_intransit(update, context)
    return ConversationHandler.END


async def fallback_arriving_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_arriving_week(update, context)
    return ConversationHandler.END


async def fallback_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await cmd_login(update, context)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Админ-команды (/logs, /delete_all_project)
# ---------------------------------------------------------------------------

async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if user_id != ALLOWED_DELETE_USER_ID:
        log.warning("/logs вызван пользователем без доступа user_id=%s", user_id)
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    log.info("/logs запрошены user_id=%s", user_id)
    try:
        if BOT_LOG_FILE.exists():
            bot_content = BOT_LOG_FILE.read_text(encoding="utf-8")
            await update.message.reply_document(
                document=BytesIO(bot_content.encode("utf-8")),
                filename="bot_logs.txt",
                caption="📋 Логи бота",
            )
        else:
            await update.message.reply_text("Файл логов бота ещё не создан.")
        secret = (os.getenv("DELETE_ALL_SECRET") or "").strip()
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{API_BASE}/api/admin/logs",
                headers={"X-Admin-Secret": secret} if secret else {},
            )
        if r.status_code == 200:
            site_content = r.text
            await update.message.reply_document(
                document=BytesIO(site_content.encode("utf-8")),
                filename="site_logs.txt",
                caption="📋 Логи сайта (backend)",
            )
        else:
            await update.message.reply_text(f"Не удалось получить логи сайта: {r.status_code}.")
    except httpx.ConnectError as e:
        log.warning("Backend недоступен при /logs: %s", e)
        await update.message.reply_text("Ошибка: backend не запущен.")
    except Exception as e:
        log.exception("Ошибка при отправке логов: %s", e)
        await update.message.reply_text(f"Ошибка: {e}")


async def cmd_delete_all_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if user_id != ALLOWED_DELETE_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Уверен", callback_data="da_confirm"),
            InlineKeyboardButton("Отмена", callback_data="da_cancel"),
        ]
    ])
    await update.message.reply_text("Вы уверены, что хотите всё удалить?", reply_markup=keyboard)


async def handle_delete_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = (query.data or "").strip()
    if not data.startswith("da_"):
        return
    user_id = update.effective_user.id if update.effective_user else None
    if user_id != ALLOWED_DELETE_USER_ID:
        await query.answer("Доступ запрещён.", show_alert=True)
        return
    await query.answer()
    if data == "da_cancel":
        try:
            await query.edit_message_text(text="Отменено.")
        except Exception:
            pass
        return
    if data == "da_confirm":
        try:
            secret = os.getenv("DELETE_ALL_SECRET", "").strip()
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{API_BASE}/api/admin/delete-all-project",
                    headers={"X-Admin-Secret": secret} if secret else {},
                )
            if r.status_code == 200:
                await query.edit_message_text(text="Запрос на удаление отправлен.")
            else:
                await query.edit_message_text(text=f"Ошибка: {r.status_code}.")
        except httpx.ConnectError:
            await query.edit_message_text(text="Ошибка: не удалось подключиться к серверу.")
        except Exception as e:
            await query.edit_message_text(text=f"Ошибка: {e}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    log.info("Запуск бота API=%s", API_BASE)
    print("Запуск бота...")
    print(f"API: {API_BASE}")

    # ConversationHandler для регистрации (/start)
    register_conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_city)],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("login", fallback_login),
        ],
    )

    # ConversationHandler для входа (/login)
    login_conv = ConversationHandler(
        entry_points=[CommandHandler("login", cmd_login)],
        states={
            LOGIN_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_username)],
            LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password)],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("intransit", fallback_intransit),
            CommandHandler("arriving_week", fallback_arriving_week),
            CommandHandler("logout", cmd_logout),
        ],
    )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(False)
        .build()
    )
    app.add_handler(register_conv)
    app.add_handler(login_conv)
    app.add_handler(CommandHandler("logout", cmd_logout))
    app.add_handler(CommandHandler("logs", cmd_logs))
    app.add_handler(CommandHandler("delete_all_project", cmd_delete_all_project))
    app.add_handler(CommandHandler("intransit", cmd_intransit))
    app.add_handler(CommandHandler("arriving_week", cmd_arriving_week))
    app.add_handler(CallbackQueryHandler(handle_intransit_callback, pattern=r"^it_"))
    app.add_handler(CallbackQueryHandler(handle_delete_all_callback, pattern=r"^da_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_message))
    # Отслеживание групп (group=1 — запускается параллельно с основными хэндлерами)
    app.add_handler(ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.TEXT, handle_group_message),
        group=1,
    )
    app.add_handler(CommandHandler("syncgroups", cmd_syncgroups))

    log.info("Бот запущен")
    print("Бот запущен. Отправьте /start в Telegram.")
    app.run_polling(
        drop_pending_updates=False,
        allowed_updates=["message", "callback_query", "my_chat_member"],
    )


if __name__ == "__main__":
    main()
