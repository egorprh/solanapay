"""
Телеграм-бот (aiogram) с машиной состояний для демонстрации платежей в сети Solana.

Функционал:
- /start — приветствие и кнопка «Поддержать разработчика»
- При нажатии — выбор суммы: 1 USDT, 1 USDC, 0.01 SOL
- После выбора — создание платежа через solana_payments и выдача инструкции + адрес
- Фоновая проверка статуса и уведомление о зачислении с ссылкой на solscan

Требования окружения:
- Переменная окружения BOT_TOKEN — токен Telegram-бота
- Для devnet: MongoDB и Redis локально, предварительно выполнить скрипт tests/setup_devnet.py

Запуск:
    Создайте файл .env рядом со скриптом:
        BOT_TOKEN=xxxxx
    Затем запустите:
        python -m bot.bot
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    raise SystemExit("Missing dependency: python-dotenv. Установите зависимости: pip install -r bot/requirements.txt")
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

if __package__:
    from .handlers import create_main_router
    from .utils import on_startup, on_shutdown
else:
    # fallback для запуска как скрипта: python bot/bot.py (на всякий случай)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from handlers import create_main_router
    from utils import on_startup, on_shutdown

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Загружаем переменные окружения.
# Предпочтительно читаем bot/.env при запуске как модуля из корня проекта,
# fallback — текущая рабочая директория.
dotenv_path = Path(__file__).resolve().parent / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)
else:
    load_dotenv()

TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
if not TELEGRAM_TOKEN:
    raise SystemExit("BOT_TOKEN не найден в .env")

bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Подключаем роутеры
main_router = create_main_router()
dp.include_router(main_router)


if __name__ == "__main__":
    async def main():
        await on_startup()
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
        finally:
            await on_shutdown()
    
    asyncio.run(main())
