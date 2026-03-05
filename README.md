# Система учёта карго-отправок

Веб-приложение для учёта карго с React-фронтендом, FastAPI бэкендом и Telegram-ботом.

## Установка

```bash
# Python-зависимости
pip install -r requirements.txt

# Frontend
cd frontend && npm install

# Корневой package (для запуска всего)
npm install
```

## Настройка

Скопируйте `.env.example` в `.env` и заполните:

- `TELEGRAM_BOT_TOKEN` — токен бота от @BotFather
- `TELEGRAM_CHAT_ID` — ID чата клиента для уведомлений
- `API_BASE_URL` — URL API (по умолчанию http://localhost:8800)

**Хранение файлов и бэкапов в S3 (рекомендуется):**  
Файлы, прикрепляемые к накладным, и бэкапы хранятся в S3, а не на диске сервера. В `.env` укажите:
- `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET`
- при необходимости `S3_ENDPOINT_URL` (например для Hostkey)

Без этих переменных загрузка файлов к накладным будет недоступна (ошибка 503).

## Резервное копирование

**При настроенном S3 (рекомендуется):**
- Кнопка «Резервная копия» создаёт бэкап в S3 (БД + снимок uploads).
- Авто-бэкап раз в 30 минут заливает БД в `backups/auto/cargo.db`.
- Список бэкапов и восстановление — через «Восстановить» → раздел «Бэкапы в S3».

**Локально (если S3 не настроен):**
- Ручная копия в `backend/backups/`, авто-копия раз в 30 мин в `cargo_auto.db`.

**S3 (Hostkey и др.):**
- Настройка в `.env`: `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET`, при необходимости `S3_ENDPOINT_URL`
- Структура: `backups/YYYY-MM-DD_HH-mm/cargo.db` + `backups/.../uploads/`; файлы накладных — `shipments/{id}/`
- **Cron** (раз в день):
  ```bash
  0 3 * * * cd /path/to/ИБРА\ ПРОЕКТ && python -m backend.scripts.s3_backup >> /var/log/cargo_s3.log 2>&1
  ```

---

## Запуск

**Важно:** команды `backend`, `frontend`, `bot` нужно запускать из **корня проекта** (папка `ИБРА ПРОЕКТ`), а не из `frontend`.

```bash
cd "C:\Users\Абдул-Азиз\Desktop\ИБРА ПРОЕКТ"

# Все сервисы сразу
npm run dev

# Или по отдельности (из корня проекта):
npm run backend   # API на http://localhost:8800
npm run frontend  # React на http://localhost:5173
npm run bot       # Telegram-бот
```

Только frontend можно запустить из своей папки:
```bash
cd frontend
npm run dev
```

## Использование

- **Главная** — все накладные, сортировка по дате
- **Закрытые накладные** — доставлено и отмена
- **Расчёт по кэшбеку** — накладные доставлены, но не рассчитаны
- **Клиенты** — список клиентов, добавление вручную (без Telegram)
- **Создать накладную** — форма создания с выбором клиента
- **Резервная копия** — ручное создание бэкапа
- **Восстановить** — восстановление из бэкапа

## Клиенты

1. **Регистрация в боте**: клиент нажимает /start, вводит ФИО и город — попадает в базу с telegram_chat_id
2. **Добавление вручную**: в разделе «Клиенты» можно добавить клиента с ФИО, городом и телефоном (без Telegram)
3. **При создании накладной**: выбрать клиента из списка или ввести телефон вручную
4. **Уведомления**: отправляются только клиентам с Telegram; при ручном телефоне уведомления недоступны

## Telegram-бот

- `/start` — регистрация клиента (ФИО, город)
- `/intransit` — накладные в дороге
- `/arriving_week` — накладные, которые приедут в течение 7 дней

---

## Деплой на сервер (Ubuntu 22.04)

1. **Скопировать проект** на сервер (git clone или архив). Установить зависимости:
   ```bash
   pip install -r requirements.txt
   cd frontend && npm ci && npm run build
   cd .. && npm install
   ```

2. **Настроить `.env`** в корне проекта (скопировать из `.env.example` и заполнить):
   - `TELEGRAM_BOT_TOKEN`, `API_BASE_URL` (на сервере: `http://127.0.0.1:8800` если бот и API на одной машине)
   - S3: `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET`, `S3_ENDPOINT_URL`
   - `DELETE_ALL_SECRET` — тот же ключ, что и локально (для команды `/delete_all_project`)
   - `CORS_ORIGINS` — URL фронта, например `https://yourdomain.com` (если фронт по другому домену)

3. **Запуск backend и бота** (через systemd или screen/tmux):
   - Backend: `uvicorn backend.main:app --host 0.0.0.0 --port 8800`
   - Бот: `python -m telegram_bot.bot`

4. **Фронт и nginx (рекомендуется):** раздавать `frontend/dist/` как статику и проксировать `/api` и `/uploads` на `http://127.0.0.1:8800`. Тогда фронт и API — один домен, CORS не мешает.

5. **Cron для бэкапа в S3** (по желанию):
   ```bash
   0 3 * * * cd /path/to/project && python -m backend.scripts.s3_backup >> /var/log/cargo_s3.log 2>&1
   ```
