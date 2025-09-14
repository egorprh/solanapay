from typing import Any
from src.core.config import settings
from src.onchain_payments.logic.database import db
from src.onchain_payments.logic.utils import logger
from redis.asyncio.client import Redis
from redis.asyncio.connection import ConnectionPool


class WalletManager:
    def __init__(self):
        self.connection_kwargs: dict[str, Any] | None = {}
        self.pool = ConnectionPool.from_url(
            f"redis://{settings.redis.host}:{settings.redis.port}/{settings.onchainpayments.redis_database}", 
            **self.connection_kwargs
        )
        self.redis = Redis(connection_pool=self.pool)

    async def get_available_wallet(self, network: str) -> str | None:        
        network_key = "evm" if network in ["polygon", "arbitrum", "optimism"] else network

        wallet_doc = await db.wallets.find_one({"network": network_key})
        
        if not wallet_doc or not wallet_doc.get("addresses"):
            return None

        addresses = wallet_doc["addresses"]

        for address in addresses:
            logger.info(f"Checking address: {address}, type: {type(address)}")

            occupied = await self.redis.get(f"occupied_wallet:{network}:{address}")
            
            logger.info(f"Occupied value from Redis for address {address}: {occupied}")
            logger.info(f"Type of occupied: {type(occupied)}")

            if not occupied:
                logger.info(f"Address {address} is available. Marking as occupied.")
                await self.redis.set(f"occupied_wallet:{network}:{address}", 1)
                return address

        logger.info("No available addresses found")
        return None


    async def release_wallet(self, network: str, address: str) -> None:
        await self.redis.delete(f"occupied_wallet:{network}:{address}")

    async def close(self) -> None:
        await self.redis.close()
        await self.pool.disconnect()
