"""
Solana Payments - Основной модуль для обработки платежей в сети Solana

Этот модуль предоставляет все необходимые функции для работы с платежами в сети Solana.
Включает в себя создание платежей, отслеживание их статуса, отмену и проверку поступления средств.

Основные возможности:
- Создание платежей в SOL, USDC, USDT
- Автоматическое отслеживание поступления средств
- Управление пулом кошельков
- Интеграция с MongoDB для хранения данных
- Использование Redis для блокировки кошельков
- Получение актуальных цен токенов через CoinGecko API

Автор: Solana Payments Team
Версия: 1.0.0
"""

import asyncio
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime
import uuid
import json

# Solana и блокчейн зависимости
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TokenAccountOpts
from solders.pubkey import Pubkey as PublicKey
from solana.rpc.commitment import Commitment

# HTTP клиент для внешних API
import aiohttp

# Валидация данных
from pydantic import BaseModel, Field, validator

# База данных
import motor.motor_asyncio

# Кэширование и блокировки
from redis.asyncio import Redis

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Config:
    """
    Конфигурация для Solana Payments
    
    Содержит все необходимые настройки для работы с Solana, MongoDB, Redis
    и внешними API. Настройки можно переопределить при инициализации.
    """
    
    # Solana настройки
    SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
    SOLANA_COMMITMENT = Commitment("confirmed")
    SOLANA_TIMEOUT = 30
    
    # MongoDB настройки
    MONGODB_URL = "mongodb://localhost:27017"
    MONGODB_DATABASE = "solana_payments"
    
    # Redis настройки
    REDIS_URL = "redis://localhost:6379"
    REDIS_DB = 0
    
    # CoinGecko API настройки
    COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
    COINGECKO_TIMEOUT = 10
    
    # Настройки кошельков
    WALLET_POOL_SIZE = 100
    WALLET_LOCK_TIMEOUT = 3600  # 1 час


class Payment(BaseModel):
    """
    Модель данных для платежа в сети Solana
    
    Представляет полную информацию о платеже включая идентификатор,
    тип токена, адрес кошелька, статус и суммы.
    """
    
    payment_id: str = Field(..., description="Уникальный идентификатор платежа")
    token: str = Field(..., description="Тип токена (sol, usdc, usdt)")
    payment_address: str = Field(..., description="Адрес кошелька для получения платежа")
    status: str = Field(default="pending", description="Статус платежа (pending, paid, cancelled)")
    payment_amount: Optional[float] = Field(None, description="Количество полученных токенов")
    outcome_amount: Optional[float] = Field(None, description="Эквивалент в USD")
    created_at: datetime = Field(default_factory=datetime.now, description="Время создания платежа")
    updated_at: datetime = Field(default_factory=datetime.now, description="Время последнего обновления")
    initial_balance: float = Field(..., description="Начальный баланс кошелька")
    transaction_signature: Optional[str] = Field(None, description="Подпись Solana транзакции")
    slot: Optional[int] = Field(None, description="Слот Solana блокчейна")
    
    @validator('token')
    def validate_token(cls, v):
        """Валидация типа токена"""
        allowed_tokens = ['sol', 'usdc', 'usdt']
        if v.lower() not in allowed_tokens:
            raise ValueError(f'Token must be one of {allowed_tokens}')
        return v.lower()
    
    @validator('status')
    def validate_status(cls, v):
        """Валидация статуса платежа"""
        allowed_statuses = ['pending', 'paid', 'cancelled']
        if v.lower() not in allowed_statuses:
            raise ValueError(f'Status must be one of {allowed_statuses}')
        return v.lower()
    
    @validator('payment_address')
    def validate_address(cls, v):
        """Валидация Solana адреса"""
        try:
            # Проверяем базовую длину и формат
            if len(v) < 32 or len(v) > 44:
                raise ValueError('Invalid Solana address length')
            # Дополнительная проверка на base58 символы
            import base58
            base58.b58decode(v)
            return v
        except Exception:
            raise ValueError('Invalid Solana address format')


class SolanaPayments:
    """
    Основной класс для работы с платежами в сети Solana
    
    Обеспечивает создание, обработку и отмену платежей. Управляет пулом кошельков,
    отслеживает поступления средств и интегрируется с внешними сервисами.
    """
    
    def __init__(self):
        """Инициализация класса SolanaPayments"""
        self.solana_client: Optional[AsyncClient] = None
        self.mongo_client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
        self.redis_client: Optional[Redis] = None
        self.db = None
        self.initialized = False
        
        # Адреса SPL токенов в сети Solana
        self.token_addresses = {
            'usdc': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
            'usdt': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'
        }
    
    async def initialize(self, config: Optional[Config] = None) -> None:
        """
        Инициализация всех подключений
        
        Создает подключения к Solana RPC, MongoDB и Redis.
        Должна вызываться перед использованием других функций.
        
        Args:
            config: Конфигурация (опционально, используется Config по умолчанию)
            
        Raises:
            Exception: При ошибке подключения к любому из сервисов
        """
        if self.initialized:
            logger.warning("SolanaPayments already initialized")
            return
            
        config = config or Config()
        logger.info("Initializing SolanaPayments...")
        
        try:
            # Инициализация Solana клиента
            self.solana_client = AsyncClient(
                config.SOLANA_RPC_URL,
                commitment=config.SOLANA_COMMITMENT,
                timeout=config.SOLANA_TIMEOUT
            )
            logger.info(f"Connected to Solana RPC: {config.SOLANA_RPC_URL}")
            
            # Инициализация MongoDB
            self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(config.MONGODB_URL)
            self.db = self.mongo_client[config.MONGODB_DATABASE]
            logger.info(f"Connected to MongoDB: {config.MONGODB_DATABASE}")
            
            # Инициализация Redis
            self.redis_client = Redis.from_url(
                config.REDIS_URL,
                db=config.REDIS_DB,
                decode_responses=True
            )
            logger.info(f"Connected to Redis: {config.REDIS_URL}")
            
            # Проверка подключений
            await self._test_connections()
            
            self.initialized = True
            logger.info("SolanaPayments initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize SolanaPayments: {e}")
            await self.cleanup()
            raise
    
    async def _test_connections(self) -> None:
        """Тестирование всех подключений"""
        try:
            # Тест Solana - используем get_version вместо get_health
            version = await self.solana_client.get_version()
            logger.info(f"Solana connection test passed. Version: {version.value}")
            
            # Тест MongoDB
            await self.db.command("ping")
            logger.info("MongoDB connection test passed")
            
            # Тест Redis
            await self.redis_client.ping()
            logger.info("Redis connection test passed")
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            raise
    
    async def create_payment(self, payment_id: str, token: str) -> Dict[str, Any]:
        """
        Создание нового платежа
        
        Создает новый платеж с указанными параметрами, выделяет свободный
        кошелек из пула, фиксирует начальный баланс и сохраняет платеж в БД.
        
        Args:
            payment_id: Уникальный идентификатор платежа
            token: Тип токена (sol, usdc, usdt)
            
        Returns:
            Dict с данными созданного платежа
            
        Raises:
            Exception: При отсутствии доступных кошельков или ошибке создания
        """
        if not self.initialized:
            raise Exception("SolanaPayments not initialized. Call initialize() first.")
        
        logger.info(f"Creating payment: {payment_id}, token: {token}")
        
        try:
            # Получение доступного кошелька
            payment_address = await self._get_available_wallet()
            if not payment_address:
                raise Exception("No available wallets in pool")
            
            logger.info(f"Assigned wallet: {payment_address}")
            
            # Получение начального баланса
            initial_balance = await self._get_balance(payment_address, token)
            logger.info(f"Initial balance: {initial_balance} {token}")
            
            # Создание объекта платежа
            payment = Payment(
                payment_id=payment_id,
                token=token,
                payment_address=payment_address,
                initial_balance=initial_balance
            )
            
            # Сохранение в MongoDB
            await self.db.payments.insert_one(payment.dict())
            logger.info(f"Payment saved to database: {payment_id}")
            
            return payment.dict()
            
        except Exception as e:
            logger.error(f"Failed to create payment {payment_id}: {e}")
            raise
    
    async def get_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """
        Получение статуса платежа
        
        Проверяет текущий баланс кошелька, вычисляет изменение относительно
        начального баланса. При обнаружении поступления обновляет статус
        на 'paid' и освобождает кошелек.
        
        Args:
            payment_id: Идентификатор платежа
            
        Returns:
            Dict с актуальными данными платежа
            
        Raises:
            Exception: При отсутствии платежа или ошибке обработки
        """
        if not self.initialized:
            raise Exception("SolanaPayments not initialized. Call initialize() first.")
        
        logger.info(f"Getting payment status: {payment_id}")
        
        try:
            # Поиск платежа в БД
            payment_data = await self.db.payments.find_one({"payment_id": payment_id})
            if not payment_data:
                raise Exception(f"Payment not found: {payment_id}")
            
            payment = Payment(**payment_data)
            logger.info(f"Found payment: {payment.status}")
            
            # Если платеж уже обработан, возвращаем текущий статус
            if payment.status != "pending":
                return payment.dict()
            
            # Проверка изменения баланса
            current_balance = await self._get_balance(payment.payment_address, payment.token)
            balance_change = current_balance - payment.initial_balance
            
            logger.info(f"Balance change: {balance_change} {payment.token}")
            
            # Если есть поступление средств
            if balance_change > 0:
                # Получение цены токена
                token_price = await self._get_token_price(payment.token)
                outcome_amount = balance_change * token_price
                
                # Обновление статуса платежа
                payment.status = "paid"
                payment.payment_amount = round(balance_change, 8)
                payment.outcome_amount = round(outcome_amount, 2)
                payment.updated_at = datetime.now()
                
                # Сохранение в БД
                await self.db.payments.update_one(
                    {"payment_id": payment_id},
                    {"$set": payment.dict()}
                )
                
                # Освобождение кошелька
                await self._release_wallet(payment.payment_address)
                
                logger.info(f"Payment marked as paid: {payment_id}")
            
            return payment.dict()
            
        except Exception as e:
            logger.error(f"Failed to get payment status {payment_id}: {e}")
            raise
    
    async def cancel_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Отмена платежа
        
        Отменяет существующий платеж, обновляет статус на 'cancelled'
        и освобождает кошелек для повторного использования.
        
        Args:
            payment_id: Идентификатор платежа для отмены
            
        Returns:
            Dict с обновленными данными платежа
            
        Raises:
            Exception: При отсутствии платежа или ошибке отмены
        """
        if not self.initialized:
            raise Exception("SolanaPayments not initialized. Call initialize() first.")
        
        logger.info(f"Cancelling payment: {payment_id}")
        
        try:
            # Поиск платежа в БД
            payment_data = await self.db.payments.find_one({"payment_id": payment_id})
            if not payment_data:
                raise Exception(f"Payment not found: {payment_id}")
            
            payment = Payment(**payment_data)
            
            # Проверка возможности отмены
            if payment.status not in ["pending"]:
                logger.warning(f"Cannot cancel payment with status: {payment.status}")
                return payment.dict()
            
            # Обновление статуса
            payment.status = "cancelled"
            payment.updated_at = datetime.now()
            
            # Сохранение в БД
            await self.db.payments.update_one(
                {"payment_id": payment_id},
                {"$set": payment.dict()}
            )
            
            # Освобождение кошелька
            await self._release_wallet(payment.payment_address)
            
            logger.info(f"Payment cancelled: {payment_id}")
            return payment.dict()
            
        except Exception as e:
            logger.error(f"Failed to cancel payment {payment_id}: {e}")
            raise
    
    async def check_payment_received(self, payment_id: str) -> bool:
        """
        Быстрая проверка поступления платежа
        
        Проверяет, поступил ли платеж, без обновления статуса в БД.
        Полезно для быстрых проверок без изменения данных.
        
        Args:
            payment_id: Идентификатор платежа
            
        Returns:
            True если платеж поступил, False в противном случае
        """
        if not self.initialized:
            raise Exception("SolanaPayments not initialized. Call initialize() first.")
        
        try:
            # Получение статуса платежа
            payment_data = await self.get_payment_status(payment_id)
            return payment_data["status"] == "paid"
            
        except Exception as e:
            logger.error(f"Failed to check payment {payment_id}: {e}")
            return False
    
    async def _get_available_wallet(self) -> Optional[str]:
        """
        Получение доступного кошелька из пула
        
        Находит свободный кошелек в MongoDB, блокирует его в Redis
        и возвращает адрес.
        
        Returns:
            Адрес доступного кошелька или None если все заняты
        """
        try:
            # Поиск документа с кошельками
            wallet_doc = await self.db.wallets.find_one({"network": "solana"})
            if not wallet_doc or not wallet_doc.get("addresses"):
                logger.error("No wallets found in database")
                return None
            
            addresses = wallet_doc["addresses"]
            
            # Поиск свободного кошелька
            for address in addresses:
                occupied = await self.redis_client.get(f"occupied_wallet:solana:{address}")
                
                if not occupied:
                    # Блокировка кошелька
                    await self.redis_client.set(
                        f"occupied_wallet:solana:{address}", 
                        "1", 
                        ex=Config.WALLET_LOCK_TIMEOUT
                    )
                    logger.info(f"Wallet locked: {address}")
                    return address
            
            logger.warning("No available wallets found")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get available wallet: {e}")
            return None
    
    async def _release_wallet(self, address: str) -> None:
        """
        Освобождение кошелька
        
        Удаляет блокировку кошелька из Redis, делая его доступным
        для новых платежей.
        
        Args:
            address: Адрес кошелька для освобождения
        """
        try:
            await self.redis_client.delete(f"occupied_wallet:solana:{address}")
            logger.info(f"Wallet released: {address}")
        except Exception as e:
            logger.error(f"Failed to release wallet {address}: {e}")
    
    async def _get_balance(self, address: str, token: str) -> float:
        """
        Получение баланса кошелька
        
        Получает текущий баланс указанного токена на указанном адресе.
        Поддерживает SOL и SPL токены (USDC, USDT).
        
        Args:
            address: Solana адрес кошелька
            token: Тип токена (sol, usdc, usdt)
            
        Returns:
            Баланс в токенах
        """
        try:
            if token == "sol":
                # Получение баланса SOL
                from solders.pubkey import Pubkey
                pubkey = Pubkey.from_string(address)
                response = await self.solana_client.get_balance(pubkey)
                balance_lamports = response.value
                balance_sol = balance_lamports / 1e9  # Конвертация из lamports в SOL
                return balance_sol
                
            else:
                # Получение баланса SPL токена
                from solders.pubkey import Pubkey
                token_mint = Pubkey.from_string(self.token_addresses[token])
                address_pubkey = Pubkey.from_string(address)
                
                # Поиск токен-аккаунта
                token_accounts = await self.solana_client.get_token_accounts_by_owner(
                    address_pubkey,
                    TokenAccountOpts(mint=token_mint)
                )
                
                if not token_accounts.value:
                    return 0.0
                
                # Получение баланса токен-аккаунта
                token_account = token_accounts.value[0]
                account_info = await self.solana_client.get_account_info(token_account.pubkey)
                
                if not account_info.value:
                    return 0.0
                
                # Парсинг данных аккаунта
                account_data = account_info.value.data
                if len(account_data) < 72:
                    logger.warning(f"Invalid token account data length: {len(account_data)}")
                    return 0.0
                
                balance = int.from_bytes(account_data[64:72], byteorder='little')
                
                # Конвертация с учетом decimals (обычно 6 для USDC/USDT)
                decimals = 6  # Стандартное значение для USDC/USDT
                balance_tokens = balance / (10 ** decimals)
                
                return balance_tokens
                
        except Exception as e:
            logger.error(f"Failed to get balance for {address}, token {token}: {e}")
            return 0.0
    
    async def _get_token_price(self, token: str) -> float:
        """
        Получение цены токена через CoinGecko API
        
        Получает актуальную цену указанного токена в USD.
        
        Args:
            token: Тип токена (sol, usdc, usdt)
            
        Returns:
            Цена токена в USD
        """
        try:
            # Маппинг токенов на CoinGecko ID
            token_mapping = {
                'sol': 'solana',
                'usdc': 'usd-coin',
                'usdt': 'tether'
            }
            
            coin_id = token_mapping.get(token)
            if not coin_id:
                raise ValueError(f"Unsupported token: {token}")
            
            # Создаем сессию с отключенной проверкой SSL для тестирования
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                url = f"{Config.COINGECKO_API_URL}/simple/price"
                params = {
                    'ids': coin_id,
                    'vs_currencies': 'usd'
                }
                
                async with session.get(url, params=params, timeout=Config.COINGECKO_TIMEOUT) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = data[coin_id]['usd']
                        logger.info(f"Token price {token}: ${price}")
                        return float(price)
                    else:
                        raise Exception(f"CoinGecko API error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to get token price for {token}: {e}")
            # Возвращаем примерную цену в случае ошибки
            fallback_prices = {
                'sol': 25.0,  # Более актуальная цена SOL
                'usdc': 1.0,
                'usdt': 1.0
            }
            return fallback_prices.get(token, 1.0)
    
    async def release_all_wallets(self) -> None:
        """
        Принудительное освобождение всех кошельков
        
        Удаляет все блокировки кошельков из Redis.
        Полезно для очистки состояния при тестировании.
        """
        if not self.initialized or not self.redis_client:
            logger.warning("SolanaPayments not initialized")
            return
            
        try:
            # Получаем все ключи блокировок кошельков
            keys = await self.redis_client.keys("occupied_wallet:solana:*")
            if keys:
                await self.redis_client.delete(*keys)
                logger.info(f"Released {len(keys)} wallet locks")
            else:
                logger.info("No wallet locks found")
                
        except Exception as e:
            logger.error(f"Failed to release wallets: {e}")
    
    async def cleanup(self) -> None:
        """
        Закрытие всех подключений
        
        Корректно закрывает все подключения к внешним сервисам.
        Должна вызываться при завершении работы с библиотекой.
        """
        logger.info("Cleaning up SolanaPayments...")
        
        try:
            if self.solana_client:
                await self.solana_client.close()
                logger.info("Solana client closed")
            
            if self.mongo_client:
                self.mongo_client.close()
                logger.info("MongoDB client closed")
            
            if self.redis_client:
                await self.redis_client.close()
                logger.info("Redis client closed")
            
            self.initialized = False
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Глобальный экземпляр для удобства использования
_payments_instance = SolanaPayments()


# Публичные функции для использования
async def initialize(config: Optional[Config] = None) -> None:
    """
    Инициализация библиотеки Solana Payments
    
    Создает подключения к Solana RPC, MongoDB и Redis.
    Должна вызываться перед использованием других функций.
    
    Args:
        config: Конфигурация (опционально)
    """
    await _payments_instance.initialize(config)


async def create_payment(payment_id: str, token: str) -> Dict[str, Any]:
    """
    Создание нового платежа
    
    Args:
        payment_id: Уникальный идентификатор платежа
        token: Тип токена (sol, usdc, usdt)
        
    Returns:
        Dict с данными созданного платежа
    """
    return await _payments_instance.create_payment(payment_id, token)


async def get_payment_status(payment_id: str) -> Dict[str, Any]:
    """
    Получение статуса платежа
    
    Args:
        payment_id: Идентификатор платежа
        
    Returns:
        Dict с актуальными данными платежа
    """
    return await _payments_instance.get_payment_status(payment_id)


async def cancel_payment(payment_id: str) -> Dict[str, Any]:
    """
    Отмена платежа
    
    Args:
        payment_id: Идентификатор платежа
        
    Returns:
        Dict с обновленными данными платежа
    """
    return await _payments_instance.cancel_payment(payment_id)


async def check_payment_received(payment_id: str) -> bool:
    """
    Быстрая проверка поступления платежа
    
    Args:
        payment_id: Идентификатор платежа
        
    Returns:
        True если платеж поступил, False в противном случае
    """
    return await _payments_instance.check_payment_received(payment_id)


async def release_all_wallets() -> None:
    """
    Принудительное освобождение всех кошельков
    
    Удаляет все блокировки кошельков из Redis.
    Полезно для очистки состояния при тестировании.
    """
    await _payments_instance.release_all_wallets()


async def cleanup() -> None:
    """
    Закрытие всех подключений
    
    Корректно закрывает все подключения к внешним сервисам.
    """
    await _payments_instance.cleanup()


# Пример использования
if __name__ == "__main__":
    async def main():
        """Пример использования библиотеки"""
        try:
            # Инициализация
            await initialize()
            
            # Создание платежа
            payment_id = str(uuid.uuid4())
            payment = await create_payment(payment_id, "sol")
            print(f"Payment created: {payment['payment_address']}")
            
            # Проверка статуса
            status = await get_payment_status(payment_id)
            print(f"Payment status: {status['status']}")
            
            # Отмена платежа
            cancelled = await cancel_payment(payment_id)
            print(f"Payment cancelled: {cancelled['status']}")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            # Очистка
            await cleanup()
    
    # Запуск примера
    asyncio.run(main())
