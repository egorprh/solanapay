from typing import Any
import uuid
import ormsgpack
import logging
from nats.aio.msg import Msg
from src.onchain_payments.logic.payments import Payments

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def handle_payment_info_request(msg: Msg):
    logger.info("Received payment info request")
    data: dict[str, Any] = ormsgpack.unpackb(msg.data)
    logger.info(f"Request data: {data}")
    payment_id = data.get("payment_id")
    if not payment_id:
        logger.error("Malformed data: payment_id missing")
        response = {
            "status": "error",
            "message": "Malformed data"
        }
        await msg.respond(ormsgpack.packb(response))
        return
    payments = Payments()
    try:
        logger.info(f"Processing payment with ID: {payment_id}")
        payment_data = await payments.process_payment(payment_id)
    except Exception as e:
        logger.error(f"Error processing payment {payment_id}: {e}")
        response = {"status": "error", "message": str(e)}
        await msg.respond(ormsgpack.packb(response))
        return
    finally:
        await payments._close_redis()
    response = {
        "status": "ok",
        "payment_id": payment_data["payment_id"],
        "payment_status": payment_data["status"],
        "payment_network": payment_data["payment_network"],
        "payment_token": payment_data["payment_token"],
        "payment_address": payment_data["payment_address"],
        "payment_amount": payment_data.get("payment_amount"),
        "outcome_amount": payment_data.get("outcome_amount")
    }
    logger.info(f"Responding with payment info: {response}")
    await msg.respond(ormsgpack.packb(response))


async def handle_payment_creation_request(msg: Msg):
    logger.info("Received payment creation request")
    data: dict[str, Any] = ormsgpack.unpackb(msg.data)
    logger.info(f"Request data: {data}")
    payment_network = data.get("payment_network")
    payment_token = data.get("payment_token")
    if not payment_network or not payment_token:
        logger.error("Malformed data: missing payment_network, payment_token")
        response = {
            "status": "error",
            "message": "Malformed data"
        }
        await msg.respond(ormsgpack.packb(response))
        return
    payments = Payments()
    try:
        payment_id = str(uuid.uuid4())
        logger.info(f"Creating payment with ID: {payment_id}, network: {payment_network}, token: {payment_token}")
        payment_data = await payments.create_payment(payment_id, payment_network, payment_token)
        response = {
            "status": "ok",
            "payment_id": payment_id,
            "payment_status": payment_data["status"],
            "payment_network": payment_data["payment_network"],
            "payment_token": payment_data["payment_token"],
            "payment_address": payment_data["payment_address"],
            "payment_amount": payment_data.get("payment_amount"),
            "outcome_amount": payment_data.get("outcome_amount")
        }
        logger.info(f"Payment created successfully: {response}")
        await msg.respond(ormsgpack.packb(response))
    except Exception as e:
        logger.error(f"Error creating payment: {e}")
        response = {
            "status": "error",
            "message": str(e)
        }
        await msg.respond(ormsgpack.packb(response))
    finally:
        await payments._close_redis()


async def handle_payment_cancellation_request(msg: Msg):
    logger.info("Received payment cancellation request")
    data: dict[str, Any] = ormsgpack.unpackb(msg.data)
    logger.info(f"Request data: {data}")
    payment_id = data.get("payment_id")
    if not payment_id:
        logger.error("Malformed data: payment_id missing")
        response = {
            "status": "error",
            "message": "Malformed data"
        }
        await msg.respond(ormsgpack.packb(response))
        return
    payments = Payments()
    try:
        logger.info(f"Cancelling payment with ID: {payment_id}")
        payment_data = await payments.cancel_payment(payment_id)
    except Exception as e:
        logger.error(f"Error cancelling payment {payment_id}: {e}")
        response = {"status": "error", "message": str(e)}
        await msg.respond(ormsgpack.packb(response))
        return
    finally:
        await payments._close_redis()
    response = {
        "status": "ok",
        "payment_id": payment_data["payment_id"],
        "payment_status": payment_data["status"],
        "payment_network": payment_data["payment_network"],
        "payment_token": payment_data["payment_token"],
        "payment_address": payment_data["payment_address"],
        "payment_amount": payment_data.get("payment_amount"),
        "outcome_amount": payment_data.get("outcome_amount")
    }
    logger.info(f"Payment cancelled successfully: {response}")
    await msg.respond(ormsgpack.packb(response))
