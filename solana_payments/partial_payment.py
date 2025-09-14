"""
Улучшения для функционала частичных платежей (исправленная версия)

Добавляет функции для автоматической отмены истекших частичных платежей
и освобождения кошельков при снятии блокировки.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class PartialPaymentManager:
    """
    Менеджер для управления частичными платежами
    
    Обеспечивает автоматическую очистку истекших частичных платежей
    и корректное освобождение кошельков.
    """
    
    def __init__(self, payments_instance):
        """
        Инициализация менеджера
        
        Args:
            payments_instance: Экземпляр SolanaPayments
        """
        self.payments = payments_instance
        # Используем Config напрямую, так как payments_instance может не иметь атрибута config
        from solana_payments import Config
        self.config = Config()
    
    async def release_expired_partial_payments(self) -> int:
        """
        Освобождение кошельков с истекшими частичными платежами
        
        Находит платежи со статусом 'partial', которые не обновлялись
        дольше WALLET_LOCK_TIMEOUT, и освобождает их кошельки.
        
        Returns:
            Количество освобожденных кошельков
        """
        if not self.payments.initialized:
            logger.warning("SolanaPayments not initialized")
            return 0
            
        try:
            # Время истечения (текущее время - TTL блокировки)
            expiry_time = datetime.now() - timedelta(seconds=self.config.WALLET_LOCK_TIMEOUT)
            
            # Поиск частичных платежей, которые не обновлялись дольше TTL
            expired_payments = await self.payments.db.payments.find({
                "status": "partial",
                "updated_at": {"$lt": expiry_time}
            })
            
            released_count = 0
            async for payment_data in expired_payments:
                # Создаем объект Payment из данных
                from solana_payments import Payment
                payment = Payment(**payment_data)
                
                # Освобождаем кошелек
                await self.payments._release_wallet(payment.payment_address)
                
                # Обновляем статус на 'cancelled'
                await self.payments.db.payments.update_one(
                    {"payment_id": payment.payment_id},
                    {
                        "$set": {
                            "status": "cancelled",
                            "updated_at": datetime.now()
                        }
                    }
                )
                
                logger.info(f"Released expired partial payment: {payment.payment_id}")
                released_count += 1
            
            if released_count > 0:
                logger.info(f"Released {released_count} expired partial payment wallets")
            
            return released_count
            
        except Exception as e:
            logger.error(f"Failed to release expired partial payments: {e}")
            return 0
    
    async def get_partial_payments_status(self) -> Dict[str, Any]:
        """
        Получение статистики по частичным платежам
        
        Returns:
            Dict с информацией о частичных платежах
        """
        if not self.payments.initialized:
            return {"error": "SolanaPayments not initialized"}
            
        try:
            # Подсчет платежей по статусам
            status_counts = await self.payments.db.payments.aggregate([
                {"$group": {"_id": "$status", "count": {"$sum": 1}}}
            ]).to_list(length=None)
            
            # Подсчет частичных платежей по времени
            now = datetime.now()
            one_hour_ago = now - timedelta(hours=1)
            
            partial_stats = await self.payments.db.payments.aggregate([
                {"$match": {"status": "partial"}},
                {"$group": {
                    "_id": None,
                    "total_partial": {"$sum": 1},
                    "recent_partial": {
                        "$sum": {
                            "$cond": [
                                {"$gte": ["$updated_at", one_hour_ago]},
                                1,
                                0
                            ]
                        }
                    },
                    "expired_partial": {
                        "$sum": {
                            "$cond": [
                                {"$lt": ["$updated_at", one_hour_ago]},
                                1,
                                0
                            ]
                        }
                    }
                }}
            ]).to_list(length=1)
            
            # Подсчет заблокированных кошельков
            locked_wallets = await self.payments.redis_client.keys("occupied_wallet:solana:*")
            
            result = {
                "timestamp": now.isoformat(),
                "status_counts": {item["_id"]: item["count"] for item in status_counts},
                "partial_payments": partial_stats[0] if partial_stats else {
                    "total_partial": 0,
                    "recent_partial": 0,
                    "expired_partial": 0
                },
                "locked_wallets_count": len(locked_wallets),
                "wallet_lock_timeout": self.config.WALLET_LOCK_TIMEOUT
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get partial payments status: {e}")
            return {"error": str(e)}
    
    async def cleanup_expired_payments(self) -> Dict[str, int]:
        """
        Полная очистка истекших платежей
        
        Returns:
            Dict с количеством очищенных платежей по типам
        """
        if not self.payments.initialized:
            return {"error": "SolanaPayments not initialized"}
            
        try:
            # Время истечения
            expiry_time = datetime.now() - timedelta(seconds=self.config.WALLET_LOCK_TIMEOUT)
            
            # Находим истекшие частичные платежи
            expired_partial = await self.payments.db.payments.find({
                "status": "partial",
                "updated_at": {"$lt": expiry_time}
            }).to_list(length=None)
            
            # Находим истекшие pending платежи (если есть)
            expired_pending = await self.payments.db.payments.find({
                "status": "pending",
                "updated_at": {"$lt": expiry_time}
            }).to_list(length=None)
            
            # Освобождаем кошельки и обновляем статусы
            partial_cancelled = 0
            pending_cancelled = 0
            
            for payment_data in expired_partial:
                from solana_payments import Payment
                payment = Payment(**payment_data)
                await self.payments._release_wallet(payment.payment_address)
                await self.payments.db.payments.update_one(
                    {"payment_id": payment.payment_id},
                    {
                        "$set": {
                            "status": "cancelled",
                            "updated_at": datetime.now()
                        }
                    }
                )
                partial_cancelled += 1
            
            for payment_data in expired_pending:
                from solana_payments import Payment
                payment = Payment(**payment_data)
                await self.payments._release_wallet(payment.payment_address)
                await self.payments.db.payments.update_one(
                    {"payment_id": payment.payment_id},
                    {
                        "$set": {
                            "status": "cancelled",
                            "updated_at": datetime.now()
                        }
                    }
                )
                pending_cancelled += 1
            
            result = {
                "partial_cancelled": partial_cancelled,
                "pending_cancelled": pending_cancelled,
                "total_cancelled": partial_cancelled + pending_cancelled
            }
            
            if result["total_cancelled"] > 0:
                logger.info(f"Cleaned up {result['total_cancelled']} expired payments")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired payments: {e}")
            return {"error": str(e)}


async def start_cleanup_scheduler(payments_instance, interval_minutes: int = 30):
    """
    Запуск периодической очистки истекших платежей
    
    Args:
        payments_instance: Экземпляр SolanaPayments
        interval_minutes: Интервал очистки в минутах
    """
    manager = PartialPaymentManager(payments_instance)
    
    logger.info(f"Starting cleanup scheduler with {interval_minutes} minute interval")
    
    while True:
        try:
            # Очистка истекших платежей
            result = await manager.cleanup_expired_payments()
            
            if "error" not in result:
                logger.info(f"Cleanup completed: {result}")
            else:
                logger.error(f"Cleanup failed: {result['error']}")
            
            # Ждем до следующей очистки
            await asyncio.sleep(interval_minutes * 60)
            
        except Exception as e:
            logger.error(f"Cleanup scheduler error: {e}")
            await asyncio.sleep(60)  # Ждем минуту при ошибке


# Пример использования
if __name__ == "__main__":
    async def main():
        from solana_payments import SolanaPayments, Config
        
        # Инициализация
        payments = SolanaPayments()
        await payments.initialize(Config())
        
        # Создание менеджера
        manager = PartialPaymentManager(payments)
        
        # Получение статистики
        status = await manager.get_partial_payments_status()
        print("Partial payments status:", status)
        
        # Очистка истекших платежей
        result = await manager.cleanup_expired_payments()
        print("Cleanup result:", result)
        
        # Запуск периодической очистки (в фоне)
        cleanup_task = asyncio.create_task(
            start_cleanup_scheduler(payments, interval_minutes=30)
        )
        
        try:
            # Основная логика приложения
            await asyncio.sleep(3600)  # Работаем час
        finally:
            cleanup_task.cancel()
            await payments.cleanup()
    
    asyncio.run(main())
