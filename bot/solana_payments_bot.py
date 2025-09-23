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
        python solana_payments_bot.py
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
import uuid
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Обеспечиваем доступность корня проекта в PYTHONPATH при запуске из папки bot
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Интеграция с Solana Payments
from solana_payments.solana_payments import (
    initialize as sp_initialize,
    create_payment as sp_create_payment,
    get_payment_status as sp_get_payment_status,
    cancel_payment as sp_cancel_payment,
    release_all_wallets as sp_release_all_wallets,
    cleanup as sp_cleanup,
    Config as SpConfig,
)


# Реестр фоновых задач опроса платежей: payment_id -> asyncio.Task
PAYMENT_TASKS: dict[str, asyncio.Task] = {}


class DonateStates(StatesGroup):
    """Состояния FSM для сценария доната."""
    idle = State()
    choosing_amount = State()
    waiting_payment = State()


def build_main_menu() -> InlineKeyboardBuilder:
    """Клавиатура с кнопкой «Поддержать разработчика»."""
    kb = InlineKeyboardBuilder()
    kb.button(text="Поддержать разработчика", callback_data="donate:start")
    kb.adjust(1)
    return kb


def build_amount_menu() -> InlineKeyboardBuilder:
    """Клавиатура выбора суммы/токена."""
    kb = InlineKeyboardBuilder()
    kb.button(text="1 USDT", callback_data="donate:amount:usdt:1")
    kb.button(text="1 USDC", callback_data="donate:amount:usdc:1")
    kb.button(text="0.01 SOL", callback_data="donate:amount:sol:0.01")
    kb.button(text="⬅️ Назад", callback_data="donate:back")
    kb.adjust(2, 2)
    return kb


def solscan_tx_url(signature: str, cluster: str = "devnet") -> str:
    """Ссылка на транзакцию в Solscan для devnet/mainnet."""
    suffix = f"?cluster={cluster}" if cluster and cluster != "mainnet" else ""
    return f"https://solscan.io/tx/{signature}{suffix}"


async def ensure_solana_payments_initialized() -> None:
    """Единоразовая инициализация solana_payments под devnet."""
    config = SpConfig()
    # используем devnet для демонстрации
    config.SOLANA_RPC_URL = "https://api.devnet.solana.com"
    # остальная конфигурация (Mongo/Redis) берётся по умолчанию: localhost
    await sp_initialize(config)


async def start_handler(message: Message, state) -> None:
    """Обработка /start — приветствие и кнопка."""
    await state.set_state(DonateStates.idle)
    text = (
        "👋 Привет! Это демонстрационный бот платежей на Solana.\n"
        "Вы можете проверить платёжную систему командой /donate.\n\n"
        "Также можете посмотреть бета-версию апки портфолио по кнопке ниже."
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="Открыть SolFolio (beta)", url="https://t.me/web3_brother_bot/solfolio")
    kb.adjust(1)
    await message.answer(text, reply_markup=kb.as_markup())


async def donate_command_handler(message: Message, state) -> None:
    """Запуск сценария доната по команде /donate."""
    await state.set_state(DonateStates.choosing_amount)
    await message.answer(
        "Выберите сумму и токен для доната: 💰",
        reply_markup=build_amount_menu().as_markup(),
    )


async def cancel_all_handler(message: Message) -> None:
    """Служебная команда для освобождения всех кошельков (reset)."""
    try:
        await ensure_solana_payments_initialized()
        # Останавливаем все фоновые задачи и отменяем платежи
        cancelled_tasks = 0
        cancelled_payments = 0
        for pid, task in list(PAYMENT_TASKS.items()):
            if task and not task.done():
                task.cancel()
                cancelled_tasks += 1
            PAYMENT_TASKS.pop(pid, None)
            try:
                await sp_cancel_payment(pid)
                cancelled_payments += 1
            except Exception:
                pass

        # Освобождаем кошельки
        await sp_release_all_wallets()
        await message.answer(
            "✅ Отменены активные платежи и остановлены проверки.\n"
            f"Задач остановлено: {cancelled_tasks}, платежей отменено: {cancelled_payments}.\n"
            "Все кошельки освобождены."
        )
    except Exception:
        await message.answer("❌ Не удалось освободить кошельки. Проверьте логи сервера.")


async def donate_start_callback(callback: CallbackQuery, state) -> None:
    """Переход к выбору суммы/токена."""
    await state.set_state(DonateStates.choosing_amount)
    await callback.message.edit_text(
        "Выберите сумму и токен для доната: 💰",
        reply_markup=build_amount_menu().as_markup(),
    )
    await callback.answer()


async def donate_back_callback(callback: CallbackQuery, state) -> None:
    """Возврат из меню сумм к стартовому сообщению."""
    await state.set_state(DonateStates.idle)
    await callback.message.edit_text(
        "👋 Привет! Это демонстрационный бот платежей на Solana.\n"
        "Чтобы сделать донат, используйте команду /donate.",
    )
    await callback.answer()


async def donate_amount_callback(callback: CallbackQuery, state) -> None:
    """Создание платежа после выбора суммы/токена и отправка инструкции."""
    try:
        _, _, token, amount_str = callback.data.split(":")
        expected_amount = float(amount_str)
    except Exception:
        await callback.answer("Некорректный выбор", show_alert=True)
        return

    await ensure_solana_payments_initialized()

    payment_id = str(uuid.uuid4())
    # Создание платежа (ожидаемая сумма — для SOL и стейблов одинаково)
    try:
        payment = await sp_create_payment(payment_id, token, expected_amount=expected_amount)
    except Exception as e:
        # Если закончились кошельки — информируем пользователя и возвращаем главное меню
        msg = str(e).lower()
        await state.set_state(DonateStates.idle)
        if "no available wallets" in msg or "no wallets" in msg:
            await callback.message.edit_text(
                "⏳ Оплата временно недоступна, попробуйте через 15 минут",
            )
            await callback.answer()
            return
        # Прочие ошибки
        await callback.message.edit_text(
            "⚠️ Произошла ошибка при создании платежа. Попробуйте позже.",
        )
        await callback.answer()
        return

    address = payment["payment_address"]
    await state.set_state(DonateStates.waiting_payment)
    # Сохраняем в состоянии необходимые поля для последующего опроса
    await state.update_data(payment_id=payment_id, token=token, expected_amount=expected_amount, address=address)

    instructions = (
        "Отправьте перевод на адрес ниже. После подтверждения сетью вы получите уведомление.\n\n"
        f"Токен: {token.upper()}\n"
        f"Сумма: {expected_amount}\n"
        f"Адрес для оплаты: `{address}`\n\n"
        "ℹ️ Как только оплата будет подтверждена, я пришлю ссылку на транзакцию в Solscan."
    )

    # Клавиатура с кнопкой отмены платежа
    kb = InlineKeyboardBuilder()
    kb.button(text="Отменить платеж", callback_data=f"donate:cancel:{payment_id}")
    kb.adjust(1)

    await callback.message.edit_text(instructions, parse_mode="Markdown", reply_markup=kb.as_markup())
    await callback.answer()

    # Запускаем фоновую задачу опроса статуса
    task = asyncio.create_task(poll_payment_and_notify(callback.message.chat.id, payment_id))
    PAYMENT_TASKS[payment_id] = task
    task.add_done_callback(lambda t, pid=payment_id: PAYMENT_TASKS.pop(pid, None))


async def donate_cancel_callback(callback: CallbackQuery, state) -> None:
    """Отмена платежа пользователем и возврат в главное меню."""
    try:
        _, action, payment_id = callback.data.split(":", 2)
    except Exception:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    # Останавливаем фоновую задачу опроса, если есть
    task = PAYMENT_TASKS.pop(payment_id, None)
    if task and not task.done():
        task.cancel()

    # Пытаемся отменить платеж через библиотеку
    try:
        await sp_cancel_payment(payment_id)
    except Exception:
        # Даже если отмена упала, возвращаем пользователя в главное меню
        pass

    await state.set_state(DonateStates.idle)
    await callback.message.edit_text(
        "🚫 Платеж отменён. Для новой оплаты используйте /donate.",
    )
    await callback.answer()


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
                signature = status.get("transaction_signature") or ""
                url = solscan_tx_url(signature, cluster="devnet") if signature else "https://solscan.io/?cluster=devnet"
                amount = status.get("paid_amount") or status.get("payment_amount")
                token = status.get("token", "sol").upper()
                text = (
                    "✅ Средства зачислены!\n\n"
                    f"Получено: {amount} {token}\n"
                    f"Ссылка на транзакцию: {url}"
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


async def on_startup() -> None:
    """Хук запуска: инициализация зависимостей Solana Payments."""
    await ensure_solana_payments_initialized()


async def on_shutdown() -> None:
    """Хук остановки: корректная очистка ресурсов Solana Payments."""
    await sp_cleanup()


def build_dispatcher() -> Dispatcher:
    """Создание и настройка диспетчера, регистрация хендлеров."""
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.register(start_handler, CommandStart())
    dp.message.register(donate_command_handler, Command("donate"))
    dp.message.register(cancel_all_handler, F.text == "/cancel_all_7890")

    dp.callback_query.register(donate_start_callback, F.data == "donate:start")
    dp.callback_query.register(donate_back_callback, F.data == "donate:back")
    dp.callback_query.register(donate_amount_callback, F.data.startswith("donate:amount:"))
    dp.callback_query.register(donate_cancel_callback, F.data.startswith("donate:cancel:"))

    return dp


async def main() -> None:
    """Точка входа: запуск aiogram-поллинга."""
    # Загружаем переменные окружения из .env
    load_dotenv()
    token: Optional[str] = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не задана переменная окружения BOT_TOKEN")

    bot = Bot(token=token)
    dp = build_dispatcher()

    await on_startup()
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())


