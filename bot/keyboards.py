"""
Функции для построения клавиатур телеграм-бота.
"""

from aiogram.utils.keyboard import InlineKeyboardBuilder


def build_main_menu() -> InlineKeyboardBuilder:
    """Клавиатура с кнопкой «Поддержать разработчика»."""
    kb = InlineKeyboardBuilder()
    kb.button(text="Поддержать разработчика", callback_data="donate:start")
    kb.adjust(1)
    return kb


def build_start_menu() -> InlineKeyboardBuilder:
    """Клавиатура для приветствия: донат и переход в портфолио."""
    kb = InlineKeyboardBuilder()
    kb.button(text="Поддержать разработчика", callback_data="donate:start")
    kb.button(text="Открыть SolFolio (beta)", url="https://t.me/web3_brother_bot/solfolio")
    kb.adjust(1, 1)
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


def build_portfolio_menu() -> InlineKeyboardBuilder:
    """Клавиатура с кнопкой для открытия SolFolio."""
    kb = InlineKeyboardBuilder()
    kb.button(text="Открыть SolFolio (beta)", url="https://t.me/web3_brother_bot/solfolio")
    kb.adjust(1)
    return kb


def build_cancel_payment_menu(payment_id: str) -> InlineKeyboardBuilder:
    """Клавиатура с кнопкой отмены платежа."""
    kb = InlineKeyboardBuilder()
    kb.button(text="Отменить платеж", callback_data=f"donate:cancel:{payment_id}")
    kb.adjust(1)
    return kb
