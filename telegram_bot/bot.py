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

REG_NAME, REG_CITY = 1, 2

# Кнопка под строкой ввода (reply keyboard)
INTRANSIT_BTN = "Товар в дороге"
REPLY_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton(INTRANSIT_BTN)]],
    resize_keyboard=True,
)

SHIPPING_LABELS = {"1_7_days": "1-7 дней", "15_20_days": "15-20 дней", "20_30_days": "20-30 дней"}


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id if update.effective_user else None
    log.info("/start chat_id=%s user_id=%s", chat_id, user_id)
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE}/api/clients/by-telegram/{chat_id}")
            if r.status_code == 200:
                data = r.json()
                log.info("Пользователь уже зарегистрирован chat_id=%s", chat_id)
                await update.message.reply_text(
                    f"✅ Вы уже зарегистрированы!\n\n"
                    f"ФИО: {data.get('full_name', '')}\n"
                    f"Город: {data.get('city', '')}\n\n"
                    f"Администратор может прикрепить вас к накладной для получения уведомлений.\n\n"
                    f"Нажмите кнопку «{INTRANSIT_BTN}» под строкой ввода, чтобы увидеть свои заказы в дороге.",
                    reply_markup=REPLY_KEYBOARD,
                )
                return ConversationHandler.END
    except httpx.ConnectError as e:
        log.warning("Backend недоступен при /start chat_id=%s: %s", chat_id, e)
    except Exception as e:
        log.exception("Ошибка при /start chat_id=%s: %s", chat_id, e)

    await update.message.reply_text(
        "👋 Добро пожаловать!\n\n"
        "Для регистрации введите ваши данные.\n"
        "Сначала напишите ваши ФИО (Фамилия Имя Отчество):"
    )
    return REG_NAME


async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = (update.message.text or "").strip()
    if not name:
        await update.message.reply_text("Пожалуйста, введите ФИО.")
        return REG_NAME
    context.user_data["reg_full_name"] = name
    await update.message.reply_text("Теперь введите ваш город:")
    return REG_CITY


async def reg_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = (update.message.text or "").strip()
    if not city:
        await update.message.reply_text("Пожалуйста, введите город.")
        return REG_CITY
    context.user_data["reg_city"] = city
    full_name = context.user_data.get("reg_full_name", "")
    chat_id = str(update.effective_chat.id)
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{API_BASE}/api/clients/register",
                json={
                    "full_name": full_name,
                    "city": city,
                    "telegram_chat_id": chat_id,
                },
            )
            r.raise_for_status()
            data = r.json()
        log.info("Регистрация успешна chat_id=%s client_id=%s", chat_id, data.get("id"))
        await update.message.reply_text(
            f"✅ Регистрация завершена!\n\n"
            f"Ваш ID: <code>{data['id']}</code>\n"
            f"ФИО: {full_name}\n"
            f"Город: {city}\n\n"
            f"Теперь администратор может прикрепить вас к накладной, "
            f"и вы будете получать уведомления об отправке и прибытии. "
            f"Кнопка «{INTRANSIT_BTN}» покажет ваши заказы в дороге.",
            parse_mode="HTML",
            reply_markup=REPLY_KEYBOARD,
        )
    except httpx.ConnectError as e:
        log.warning("Backend недоступен при регистрации chat_id=%s: %s", chat_id, e)
        await update.message.reply_text(
            "Ошибка: не удалось подключиться к серверу.\n\n"
            "Запустите backend из корня проекта:\n"
            "cd \"ИБРА ПРОЕКТ\"\n"
            "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8800\n\n"
            "Или дважды кликните run_backend.bat"
        )
    except Exception as e:
        log.exception("Ошибка регистрации chat_id=%s: %s", chat_id, e)
        await update.message.reply_text(f"Ошибка регистрации: {e}")
    context.user_data.clear()
    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Регистрация отменена.")
    return ConversationHandler.END


async def fallback_intransit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_intransit(update, context)
    return ConversationHandler.END


async def fallback_arriving_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_arriving_week(update, context)
    return ConversationHandler.END


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
    """Одна строка для списка: название, трекинг, дата, вид, вес, сумма, статус."""
    st = s.get("shipping_type", "")
    title = (s.get("title") or "Без названия")[:40]
    tracking = s.get("tracking") or "—"
    date = s.get("dispatch_date") or "—"
    kind = SHIPPING_LABELS.get(st, st)
    weight = s.get("weight", 0)
    amount = s.get("amount_to_pay", 0)
    status = "в дороге"
    return f"{index}) {title}, {tracking}, {date}, {kind}, {weight} кг, {amount}, {status}"


def format_shipment_detail(s: dict) -> str:
    """Подробная карточка заказа."""
    base = format_shipment(s)
    extra = []
    if s.get("product_list"):
        extra.append(f"Состав: {s['product_list']}")
    if s.get("notes"):
        extra.append(f"Примечание: {s['notes']}")
    if extra:
        base += "\n\n" + "\n".join(extra)
    return base


async def fetch_in_transit_by_telegram(chat_id: str):
    """Накладные «в дороге», закреплённые за клиентом по telegram_chat_id."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_BASE}/api/shipments/in-transit-by-telegram/{chat_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


async def fetch_shipment_by_tracking(chat_id: str, tracking: str):
    """Один заказ по трекингу только если он привязан к этому telegram."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{API_BASE}/api/shipments/by-tracking",
            params={"tracking": tracking.strip(), "telegram_chat_id": chat_id},
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


def _build_intransit_text(shipments_slice: list, total_count: int, total_sum: float, page: int, total_pages: int) -> str:
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


def _build_intransit_keyboard(shipments_slice: list, page: int, total_pages: int):
    """До 8 кнопок: 1–6 (по 2 в ряду), затем Вперёд/Назад при необходимости."""
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
    """Обработка кнопки «Товар в дороге» под строкой ввода: список заказов клиента с пагинацией."""
    chat_id = str(update.effective_chat.id)
    try:
        shipments = await fetch_in_transit_by_telegram(chat_id)
        if shipments is None:
            await update.message.reply_text(
                "Сначала зарегистрируйтесь: отправьте /start и введите ФИО и город.",
            )
            return
        if not shipments:
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
    """Callback: it_page_N — перелистовать; it_detail_<id> — показать заказ подробно."""
    query = update.callback_query
    data = (query.data or "").strip()
    if not data.startswith("it_"):
        return
    await query.answer()
    chat_id = str(update.effective_chat.id)
    if data.startswith("it_detail_"):
        shipment_id = data.replace("it_detail_", "", 1)
        shipments = context.user_data.get("intransit_list") or []
        shipment = next((s for s in shipments if s.get("id") == shipment_id), None)
        if shipment:
            text = format_shipment_detail(shipment)
            await query.message.reply_text(text, parse_mode="HTML")
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
        slice_ = shipments[start : start + 6]
        total_count = len(shipments)
        total_sum = sum(float(s.get("amount_to_pay") or 0) for s in shipments)
        text = _build_intransit_text(slice_, total_count, total_sum, page, total_pages)
        keyboard = _build_intransit_keyboard(slice_, page, total_pages)
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard)
        except Exception:
            pass
        return


def _looks_like_tracking(text: str) -> bool:
    """Текст похож на трекинг: не команда, без пробелов или одна строка, длина от 4."""
    if not text or len(text) > 80:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.startswith("/"):
        return False
    if re.search(r"[\s\n]", stripped):
        return False
    return len(stripped) >= 4 and bool(re.search(r"[a-zA-Z0-9]", stripped))


async def handle_tracking_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь ввёл в чат трекинг — ищем заказ по трекингу + telegram (только свои)."""
    text = (update.message.text or "").strip()
    if not _looks_like_tracking(text):
        return
    chat_id = str(update.effective_chat.id)
    try:
        shipment = await fetch_shipment_by_tracking(chat_id, text)
        if shipment is None:
            await update.message.reply_text("Заказ не найден или не привязан к вашему аккаунту.")
            return
        total_sum = float(shipment.get("amount_to_pay") or 0)
        total_count = 1
        context.user_data["intransit_list"] = [shipment]
        context.user_data["intransit_total_pages"] = 1
        slice_ = [shipment]
        msg_text = _build_intransit_text(slice_, total_count, total_sum, 1, 1)
        keyboard = _build_intransit_keyboard(slice_, 1, 1)
        await update.message.reply_text(msg_text, reply_markup=keyboard)
        log.debug("Поиск по трекингу chat_id=%s tracking=%s", chat_id, text)
    except httpx.ConnectError as e:
        log.warning("Backend недоступен (трекинг) chat_id=%s: %s", chat_id, e)
        await update.message.reply_text("Ошибка: backend не запущен.")
    except Exception as e:
        log.exception("Ошибка поиска по трекингу chat_id=%s: %s", chat_id, e)
        await update.message.reply_text(f"Ошибка: {e}")


async def cmd_intransit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /intransit: для обратной совместимости — показывает заказы в дороге (по telegram)."""
    await handle_intransit_button(update, context)


async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Текст от пользователя: кнопка «Товар в дороге» или поиск по трекингу."""
    text = (update.message.text or "").strip()
    if text == INTRANSIT_BTN:
        await handle_intransit_button(update, context)
        return
    if _looks_like_tracking(text):
        await handle_tracking_search(update, context)


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
    try:
        shipments = await fetch_shipments(status="in_transit", order="desc")
        today = date.today()
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


async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /logs — только для user 1338143348. Отправляет два файла: логи бота и логи сайта."""
    user_id = update.effective_user.id if update.effective_user else None
    if user_id != ALLOWED_DELETE_USER_ID:
        log.warning("/logs вызван пользователем без доступа user_id=%s", user_id)
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    log.info("/logs запрошены user_id=%s", user_id)
    try:
        # 1) Файл логов бота
        if BOT_LOG_FILE.exists():
            bot_content = BOT_LOG_FILE.read_text(encoding="utf-8")
            await update.message.reply_document(
                document=BytesIO(bot_content.encode("utf-8")),
                filename="bot_logs.txt",
                caption="📋 Логи бота",
            )
        else:
            await update.message.reply_text("Файл логов бота ещё не создан (bot_logs.txt).")
        # 2) Логи сайта с API
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
            await update.message.reply_text(f"Не удалось получить логи сайта: {r.status_code}. Проверьте backend и DELETE_ALL_SECRET.")
            log.warning("GET /api/admin/logs вернул %s", r.status_code)
    except httpx.ConnectError as e:
        log.warning("Backend недоступен при /logs: %s", e)
        await update.message.reply_text("Ошибка: backend не запущен. Логи сайта недоступны.")
    except Exception as e:
        log.exception("Ошибка при отправке логов: %s", e)
        await update.message.reply_text(f"Ошибка: {e}")


async def cmd_delete_all_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /delete_all_project — только для пользователя с id 1338143348."""
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
    await update.message.reply_text(
        "Вы уверены, что хотите всё удалить?",
        reply_markup=keyboard,
    )


async def handle_delete_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок подтверждения удаления всего проекта."""
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
                await query.edit_message_text(text="Запрос на удаление отправлен. Сервер выполняет очистку.")
            else:
                await query.edit_message_text(text=f"Ошибка: {r.status_code}. Проверьте DELETE_ALL_SECRET в .env на сервере.")
        except httpx.ConnectError:
            await query.edit_message_text(text="Ошибка: не удалось подключиться к серверу.")
        except Exception as e:
            await query.edit_message_text(text=f"Ошибка: {e}")


def main():
    log.info("Запуск бота API=%s", API_BASE)
    print("Запуск бота...")
    print(f"API: {API_BASE}")

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_city)],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("intransit", fallback_intransit),
            CommandHandler("arriving_week", fallback_arriving_week),
        ],
    )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(False)
        .build()
    )
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("logs", cmd_logs))
    app.add_handler(CommandHandler("delete_all_project", cmd_delete_all_project))
    app.add_handler(CommandHandler("intransit", cmd_intransit))
    app.add_handler(CommandHandler("arriving_week", cmd_arriving_week))
    app.add_handler(CallbackQueryHandler(handle_delete_all_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_message))
    app.add_handler(CallbackQueryHandler(handle_intransit_callback))

    log.info("Бот запущен")
    print("Бот запущен. Отправьте /start в Telegram.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
