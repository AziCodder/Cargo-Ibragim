@echo off
cd /d "%~dp0"
echo Starting Telegram bot...
python telegram_bot/bot.py
pause
