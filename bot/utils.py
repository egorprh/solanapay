"""
Вспомогательные функции для телеграм-бота платежей Solana.
"""

import asyncio
import os
import sys
import io
import csv
import json
from datetime import datetime
from typing import List, Dict

from aiogram import Bot
from aiogram.types import BufferedInputFile
import motor.motor_asyncio
from bson import ObjectId

# Добавляем путь к родительской директории для импорта solana_payments
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _mongo_url() -> str:
    return os.getenv("MONGODB_URL", "mongodb://localhost:27017")


def _mongo_db() -> str:
    return os.getenv("MONGODB_DATABASE", "solana_payments")


def _redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379")

from solana_payments.solana_payments import (
    initialize as sp_initialize,
    get_payment_status as sp_get_payment_status,
    cancel_payment as sp_cancel_payment,
    release_all_wallets as sp_release_all_wallets,
    cleanup as sp_cleanup,
    Config as SpConfig,
)

TEST_WALLETS: List[str] = [
    "3PmrYZ9KD3GLLnmGjJYcuGmt3zq2BBG34JLUhoUv7ZSL",
    "2kDfwYtSYiG18WJiTpsBKzBqAhVvDNhJjwvjw3nVsNN8",
    "DppBmsoG5ciXsYMnMmdmGicGHepd36oZ6hwVysTTYyrk",
    "EpufTXUZmndCdMX5CSwLTPeWbEVvpbbjjQMYSS7TDxYM",
]


def _seed_wallets_db_payload() -> Dict[str, object]:
    return {
        "network": "solana",
        "addresses": TEST_WALLETS,
        "created_at": "2024-01-01T00:00:00Z",
        "description": "Default wallet pool for production",
    }


async def ensure_solana_payments_initialized() -> None:
    """Единоразовая инициализация solana_payments под mainnet."""
    config = SpConfig()
    # используем mainnet
    config.SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    # Подключения к сервисам внутри docker-compose
    config.MONGODB_URL = _mongo_url()
    config.MONGODB_DATABASE = _mongo_db()
    config.REDIS_URL = _redis_url()
    await sp_initialize(config)


async def ensure_database_initialized() -> None:
    """Идемпотентная инициализация БД: создаёт данные только если их нет."""
    mongo_url = _mongo_url()
    mongo_db = _mongo_db()
    client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
    db = client[mongo_db]
    try:
        # Идемпотентная инициализация индексов
        await db.payments.create_index("payment_id", unique=True)
        await db.payments.create_index("status")
        await db.payments.create_index("created_at")
        await db.payments.create_index("payment_address")
        await db.wallets.create_index("network", unique=True)

        # Если документ с кошельками уже есть — ничего не делаем
        exists = await db.wallets.find_one({"network": "solana"})
        if exists:
            return

        # Иначе создаём пул кошельков под продакшн
        await db.wallets.insert_one(_seed_wallets_db_payload())
    finally:
        client.close()


async def poll_payment_and_notify(chat_id: int, payment_id: str, check_interval_sec: int = 5, max_checks: int = 360) -> None:
    """Фоновый опрос статуса платежа и уведомление при успешном зачислении.

    По умолчанию ждём ~30 минут (check_interval_sec * max_checks).
    """
    # Создаём бота локально (без диспетчера), чтобы отправить уведомление из фоновой задачи
    bot = Bot(token=os.environ["BOT_TOKEN"])  # KeyError даст явную ошибку при отсутствии
    try:
        # Небольшая задержка перед первым опросом, чтобы сеть успела обработать перевод
        await asyncio.sleep(check_interval_sec)
        for _ in range(max_checks):
            status = await sp_get_payment_status(payment_id)
            st = status.get("status")
            if st == "cancelled":
                # Платёж отменён где-то ещё — завершаем задачу и уведомим пользователя
                await bot.send_message(chat_id, "🚫 Платёж отменён. При необходимости создайте новый.")
                break
            if st in ("paid", "overpaid"):
                amount = status.get("paid_amount") or status.get("payment_amount")
                token = status.get("token", "sol").upper()
                text = (
                    "✅ Средства зачислены!\n\n"
                    "🙏 Спасибо за донат!\n\n"
                    f"Получено: {amount} {token}\n"
                )
                await bot.send_message(chat_id, text)
                break
            await asyncio.sleep(check_interval_sec)
        else:
            # Истёк таймаут ожидания: пробуем отменить платеж и уведомляем пользователя
            try:
                await sp_cancel_payment(payment_id)
            except Exception:
                pass
            await bot.send_message(
                chat_id,
                "⏱ Время ожидания истекло. Платеж отменён. Запросите оплату по новой.",
            )
    except Exception:
        # В целях простоты демо — подавляем исключения фонового таска
        pass
    finally:
        await bot.session.close()


def _serialize_value(value):
    """Приведение значений Mongo к строкам для CSV."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    return value


def _generate_csv_from_documents(documents: list[dict]) -> bytes:
    """Формирует CSV из произвольных документов MongoDB. Возвращает bytes UTF-8."""
    if not documents:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["empty"])  # чтобы файл не был пустым
        return output.getvalue().encode("utf-8")

    # Собираем все ключи
    all_keys: set[str] = set()
    for doc in documents:
        all_keys.update(doc.keys())
    # Приводим к детерминированному порядку колонок
    fieldnames = sorted(all_keys)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for doc in documents:
        flat: dict[str, str] = {}
        for key in fieldnames:
            value = doc.get(key)
            flat[key] = _serialize_value(value)
        writer.writerow(flat)
    return output.getvalue().encode("utf-8")


def _generate_wallets_csv(wallet_docs: list[dict]) -> bytes:
    """Формирует CSV для коллекции wallets: по одному ряду на адрес."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["network", "address", "index", "_id"])
    for doc in wallet_docs:
        network = doc.get("network")
        addresses = doc.get("addresses") or []
        mongo_id = str(doc.get("_id")) if doc.get("_id") is not None else ""
        if isinstance(addresses, list):
            for idx, addr in enumerate(addresses):
                writer.writerow([_serialize_value(network), _serialize_value(addr), idx, mongo_id])
        else:
            writer.writerow([_serialize_value(network), _serialize_value(addresses), "", mongo_id])
    return output.getvalue().encode("utf-8")


async def get_data_handler(message) -> None:
    """Экспорт коллекций wallets и payments в виде двух CSV-файлов."""
    try:
        mongo_url = _mongo_url()
        mongo_db = _mongo_db()
        client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
        db = client[mongo_db]

        wallets_cursor = db.wallets.find({})
        payments_cursor = db.payments.find({})

        wallets_docs = await wallets_cursor.to_list(length=None)
        payments_docs = await payments_cursor.to_list(length=None)

        wallets_csv = _generate_wallets_csv(wallets_docs)
        payments_csv = _generate_csv_from_documents(payments_docs)

        wallets_file = BufferedInputFile(wallets_csv, filename="wallets.csv")
        payments_file = BufferedInputFile(payments_csv, filename="payments.csv")

        await message.answer_document(document=wallets_file, caption="wallets.csv")
        await message.answer_document(document=payments_file, caption="payments.csv")
    except Exception:
        await message.answer("❌ Не удалось сформировать CSV. Проверьте логи сервера.")
    finally:
        if "client" in locals():
            client.close()


async def on_startup() -> None:
    """Хук запуска: инициализация зависимостей Solana Payments."""
    # Сначала идемпотентно убедимся, что БД подготовлена (индексы и пул кошельков)
    await ensure_database_initialized()
    await ensure_solana_payments_initialized()


async def on_shutdown() -> None:
    """Хук остановки: корректная очистка ресурсов Solana Payments."""
    await sp_cleanup()
