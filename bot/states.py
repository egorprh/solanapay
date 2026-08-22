"""
Состояния FSM для телеграм-бота платежей Solana.
"""

from aiogram.fsm.state import State, StatesGroup


class DonateStates(StatesGroup):
    """Состояния FSM для сценария доната."""
    idle = State()
    choosing_amount = State()
    waiting_payment = State()
