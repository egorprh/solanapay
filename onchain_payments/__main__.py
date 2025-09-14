import asyncio
from typing import Optional
from nats import connect, NATS
from src.onchain_payments.handlers import (
    handle_payment_info_request,
    handle_payment_creation_request,
    handle_payment_cancellation_request
)
from src.core.nats.adapter import NatsAdapter
from src.core.config import settings


async def main() -> None:
    """
    Главная функция приложения OnChain Payments Service.
    
    Инициализирует NATS соединение, подписывается на сообщения для обработки
    платежей и запускает бесконечный цикл ожидания сообщений. Обрабатывает
    три типа запросов: создание, получение информации и отмена платежей.
    
    Returns:
        None: Функция работает бесконечно до принудительной остановки
        
    Raises:
        Exception: При ошибке подключения к NATS или обработки сообщений
        
    Example:
        Запуск сервиса:
        >>> asyncio.run(main())
        
    Note:
        Сервис подписывается на следующие NATS subjects:
        - onchain_payments.payment.create
        - onchain_payments.payment.get  
        - onchain_payments.payment.cancel
        
        При завершении работы корректно закрывает все соединения.
    """
    nats_adapter = NatsAdapter(
        connect,
        f"nats://{settings.nats.host}:{settings.nats.port}"
    )
    session: Optional[NATS] = None
    try:
        session = await nats_adapter.open_nats_session()
        # stream = session.jetstream()
        # await stream.add_stream(
        #     name="bot",
        #     subjects=[
        #         "bot",
        #         "bot.digest",
        #         "bot.digest.generate"
        #     ]
        # )
        get = await session.subscribe(
            "onchain_payments.payment.get",
            cb=handle_payment_info_request
        )
        create = await session.subscribe(
            "onchain_payments.payment.create",
            cb=handle_payment_creation_request
        )
        cancel = await session.subscribe(
            "onchain_payments.payment.cancel",
            cb=handle_payment_cancellation_request
        )
        await session.flush()
        try:
            await asyncio.Event().wait()
        finally:
            await get.unsubscribe()
            await create.unsubscribe()
            await cancel.unsubscribe()
    finally:
        if session is not None:
            await session.drain()
            await session.close()


asyncio.run(main())
