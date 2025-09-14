import asyncio
from nats import connect, NATS
from src.onchain_payments.handlers import (
    handle_payment_info_request,
    handle_payment_creation_request,
    handle_payment_cancellation_request
)
from src.core.nats.adapter import NatsAdapter
from src.core.config import settings


async def main() -> None:
    nats_adapter = NatsAdapter(
        connect,
        f"nats://{settings.nats.host}:{settings.nats.port}"
    )
    session: NATS | None = None
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
