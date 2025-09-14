from typing import Any, Optional
from src.core.config import settings
from src.onchain_payments.logic.database import db
from src.onchain_payments.logic.utils import logger
from redis.asyncio.client import Redis
from redis.asyncio.connection import ConnectionPool


class WalletManager:
    """
    Менеджер кошельков для управления пулом адресов в различных блокчейн-сетях.
    
    Обеспечивает выделение и освобождение кошельков для обработки платежей,
    используя Redis для координации состояния между экземплярами сервиса.
    Поддерживает EVM-совместимые сети (объединенные в группу 'evm') и Solana.
    """
    
    def __init__(self) -> None:
        """
        Инициализация менеджера кошельков.
        
        Создает подключение к Redis для управления состоянием кошельков.
        Настраивает пул подключений и Redis клиент для асинхронных операций.
        
        Raises:
            Exception: При ошибке подключения к Redis или создания пула подключений
            
        Note:
            Использует настройки из src.core.config.settings для подключения к Redis.
            Пул подключений создается с параметрами по умолчанию.
        """
        self.connection_kwargs: dict[str, Any] | None = {}
        self.pool = ConnectionPool.from_url(
            f"redis://{settings.redis.host}:{settings.redis.port}/{settings.onchainpayments.redis_database}", 
            **self.connection_kwargs
        )
        self.redis = Redis(connection_pool=self.pool)

    async def get_available_wallet(self, network: str) -> Optional[str]:
        """
        Получение доступного кошелька для указанной сети.
        
        Находит свободный кошелек в пуле для указанной сети, блокирует его
        в Redis и возвращает адрес. EVM-совместимые сети (polygon, arbitrum, 
        optimism) объединяются в группу 'evm' для использования общего пула кошельков.
        
        Args:
            network (str): Название сети (polygon, arbitrum, optimism, solana)
            
        Returns:
            Optional[str]: Адрес доступного кошелька или None, если все заняты
            
        Raises:
            Exception: При ошибке подключения к MongoDB или Redis
            
        Example:
            >>> wallet_manager = WalletManager()
            >>> address = await wallet_manager.get_available_wallet("ethereum")
            >>> if address:
            ...     print(f"Available wallet: {address}")
            ... else:
            ...     print("No available wallets")
            
        Note:
            Метод автоматически блокирует найденный кошелек в Redis с ключом
            'occupied_wallet:{network}:{address}' для предотвращения повторного использования.
        """
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
        """
        Освобождение кошелька для повторного использования.
        
        Удаляет блокировку кошелька из Redis, делая его доступным для
        новых платежей. Вызывается после завершения или отмены платежа.
        
        Args:
            network (str): Название сети, к которой принадлежит кошелек
            address (str): Адрес кошелька для освобождения
            
        Returns:
            None
            
        Raises:
            Exception: При ошибке подключения к Redis
            
        Example:
            >>> wallet_manager = WalletManager()
            >>> await wallet_manager.release_wallet("ethereum", "0x1234...")
            
        Note:
            Метод удаляет ключ 'occupied_wallet:{network}:{address}' из Redis.
            После вызова этого метода кошелек становится доступным для новых платежей.
        """
        await self.redis.delete(f"occupied_wallet:{network}:{address}")

    async def close(self) -> None:
        """
        Корректное закрытие соединений с Redis.
        
        Закрывает Redis клиент и отключает пул подключений для
        освобождения ресурсов. Должен вызываться при завершении работы
        с менеджером кошельков.
        
        Returns:
            None
            
        Raises:
            Exception: При ошибке закрытия соединений
            
        Example:
            >>> wallet_manager = WalletManager()
            >>> # ... использование менеджера ...
            >>> await wallet_manager.close()
            
        Note:
            Метод должен вызываться в блоке finally или при завершении
            работы приложения для корректного освобождения ресурсов.
        """
        await self.redis.close()
        await self.pool.disconnect()
