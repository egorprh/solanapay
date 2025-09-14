"""
Solana Payments Library

Библиотека для обработки платежей в сети Solana.
Предоставляет простые функции для создания, отслеживания и отмены платежей.

Основные функции:
- create_payment: создание нового платежа
- get_payment_status: получение статуса платежа
- cancel_payment: отмена платежа
- check_payment_received: проверка поступления средств

Пример использования:
    import asyncio
    from solana_payments import initialize, create_payment, get_payment_status, cleanup
    
    async def main():
        await initialize()
        payment = await create_payment("uuid-123", "sol")
        status = await get_payment_status("uuid-123")
        await cleanup()
    
    asyncio.run(main())
"""

from .solana_payments import (
    initialize,
    create_payment,
    get_payment_status,
    cancel_payment,
    check_payment_received,
    release_all_wallets,
    cleanup
)

__version__ = "1.0.0"
__author__ = "Solana Payments Team"

__all__ = [
    "initialize",
    "create_payment", 
    "get_payment_status",
    "cancel_payment",
    "check_payment_received",
    "release_all_wallets",
    "cleanup"
]
