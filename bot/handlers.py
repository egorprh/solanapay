"""
Обработчики для телеграм-бота платежей Solana.
"""

import asyncio
import uuid

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import CallbackQuery, Message

# Добавляем путь к родительской директории для импорта solana_payments
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from solana_payments.solana_payments import (
    create_payment as sp_create_payment,
    cancel_payment as sp_cancel_payment,
    release_all_wallets as sp_release_all_wallets,
)

from .states import DonateStates
from .keyboards import (
    build_amount_menu,
    build_start_menu,
    build_cancel_payment_menu,
)
from .utils import (
    ensure_solana_payments_initialized,
    poll_payment_and_notify,
    get_data_handler,
)

# Реестр фоновых задач опроса платежей: payment_id -> asyncio.Task
PAYMENT_TASKS: dict[str, asyncio.Task] = {}


async def start_handler(message: Message, state) -> None:
    """Обработка /start — приветствие и кнопка."""
    await state.set_state(DonateStates.idle)
    text = (
        "👋 Привет! Это демонстрационный бот платежей на Solana.\n"
        "Вы можете проверить платёжную систему командой /donate.\n\n"
        "Также можете посмотреть бета-версию портфолио по кнопке ниже."
    )
    await message.answer(text, reply_markup=build_start_menu().as_markup())


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
        "Чтобы сделать донат, используйте /donate.",
        reply_markup=build_start_menu().as_markup(),
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
        f"Сеть: SOL\n"
        f"Адрес для оплаты: `{address}`"
    )

    await callback.message.edit_text(instructions, parse_mode="Markdown", reply_markup=build_cancel_payment_menu(payment_id).as_markup())
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


def create_main_router() -> Router:
    """Создание и настройка основного роутера с обработчиками."""
    router = Router()
    
    # Команды
    router.message.register(start_handler, CommandStart())
    router.message.register(donate_command_handler, Command("donate"))
    router.message.register(cancel_all_handler, Command("cancel_all_7890"))
    router.message.register(get_data_handler, Command("get_data_7890"))

    # Callback queries
    router.callback_query.register(donate_start_callback, F.data == "donate:start")
    router.callback_query.register(donate_back_callback, F.data == "donate:back")
    router.callback_query.register(donate_amount_callback, F.data.startswith("donate:amount:"))
    router.callback_query.register(donate_cancel_callback, F.data.startswith("donate:cancel:"))
    
    return router
