#!/usr/bin/env python3
"""
Тесты для очистки истекших частичных платежей (исправленная версия)

Проверяет работу функций:
- release_expired_partial_payments
- get_partial_payments_status
- cleanup_expired_payments
- start_cleanup_scheduler
"""

import asyncio
import uuid
import logging
import sys
import os
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solana_payments import SolanaPayments, Config
from partial_payment import PartialPaymentManager, start_cleanup_scheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_partial_payment_cleanup():
    """Тест очистки истекших частичных платежей"""
    
    try:
        logger.info("🚀 Starting partial payment cleanup tests")
        logger.info("=" * 60)
        
        # Инициализация
        logger.info("🔧 Initializing Solana Payments...")
        payments = SolanaPayments()
        await payments.initialize(Config())
        logger.info("✅ Initialization complete")
        
        # Создание менеджера
        manager = PartialPaymentManager(payments)
        
        # Тест 1: Создание частичного платежа
        logger.info("\n🧪 Test 1: Creating partial payment...")
        payment_id = str(uuid.uuid4())
        expected_amount = 100.0
        
        payment = await payments.create_payment(payment_id, "sol", expected_amount)
        logger.info(f"✅ Payment created: {payment['payment_id']}")
        
        # Тест 2: Получение статистики до очистки
        logger.info("\n🧪 Test 2: Getting partial payments status...")
        status = await manager.get_partial_payments_status()
        logger.info(f"✅ Status before cleanup:")
        logger.info(f"   Status counts: {status.get('status_counts', {})}")
        logger.info(f"   Partial payments: {status.get('partial_payments', {})}")
        logger.info(f"   Locked wallets: {status.get('locked_wallets_count', 0)}")
        
        # Тест 3: Имитация истекшего платежа (изменяем updated_at в БД)
        logger.info("\n🧪 Test 3: Simulating expired payment...")
        expired_time = datetime.now() - timedelta(seconds=Config.WALLET_LOCK_TIMEOUT + 3600)  # 2 часа назад
        
        await payments.db.payments.update_one(
            {"payment_id": payment_id},
            {"$set": {"updated_at": expired_time}}
        )
        logger.info(f"✅ Payment marked as expired (updated_at: {expired_time})")
        
        # Тест 4: Очистка истекших платежей
        logger.info("\n🧪 Test 4: Cleaning up expired payments...")
        cleanup_result = await manager.cleanup_expired_payments()
        logger.info(f"✅ Cleanup result: {cleanup_result}")
        
        # Тест 5: Проверка статуса после очистки
        logger.info("\n🧪 Test 5: Checking status after cleanup...")
        status_after = await manager.get_partial_payments_status()
        logger.info(f"✅ Status after cleanup:")
        logger.info(f"   Status counts: {status_after.get('status_counts', {})}")
        logger.info(f"   Partial payments: {status_after.get('partial_payments', {})}")
        logger.info(f"   Locked wallets: {status_after.get('locked_wallets_count', 0)}")
        
        # Тест 6: Проверка, что платеж отменен
        logger.info("\n🧪 Test 6: Verifying payment cancellation...")
        final_status = await payments.get_payment_status(payment_id)
        logger.info(f"✅ Final payment status: {final_status['status']}")
        
        if final_status['status'] == 'cancelled':
            logger.info("✅ Payment successfully cancelled")
        else:
            logger.error(f"❌ Expected 'cancelled', got '{final_status['status']}'")
        
        logger.info("\n🎉 All cleanup tests completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise
    finally:
        logger.info("\n🧹 Cleaning up...")
        await payments.cleanup()
        logger.info("✅ Cleanup complete")


async def test_cleanup_scheduler():
    """Тест планировщика очистки"""
    
    try:
        logger.info("🚀 Starting cleanup scheduler test")
        logger.info("=" * 60)
        
        # Инициализация
        payments = SolanaPayments()
        await payments.initialize(Config())
        
        # Создание менеджера
        manager = PartialPaymentManager(payments)
        
        # Тест 1: Запуск планировщика на короткий период
        logger.info("\n🧪 Test 1: Starting cleanup scheduler...")
        
        # Запускаем планировщик с интервалом 10 секунд
        cleanup_task = asyncio.create_task(
            start_cleanup_scheduler(payments, interval_minutes=0.17)  # ~10 секунд
        )
        
        # Ждем 15 секунд
        logger.info("⏳ Waiting 15 seconds for scheduler to run...")
        await asyncio.sleep(15)
        
        # Отменяем задачу
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            logger.info("✅ Scheduler task cancelled successfully")
        
        logger.info("🎉 Cleanup scheduler test completed!")
        
    except Exception as e:
        logger.error(f"❌ Scheduler test failed: {e}")
        raise
    finally:
        logger.info("\n🧹 Cleaning up...")
        await payments.cleanup()
        logger.info("✅ Cleanup complete")


async def main():
    """Главная функция для запуска тестов"""
    print("🧪 Solana Payments Partial Payment Cleanup Test Suite (Fixed)")
    print("=" * 60)
    print("⚠️  ВНИМАНИЕ: Этот тест проверяет логику очистки истекших платежей")
    print("💰 Требуется подключение к MongoDB и Redis")
    print("=" * 60)
    
    try:
        # Тест очистки
        await test_partial_payment_cleanup()
        
        # Небольшая пауза между тестами
        await asyncio.sleep(2)
        
        # Тест планировщика
        await test_cleanup_scheduler()
        
    except KeyboardInterrupt:
        print("\n⏹️  Тесты прерваны пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        print("\n🔧 Возможные причины:")
        print("1. MongoDB или Redis недоступны")
        print("2. Проблемы с подключением к Solana RPC")
        print("3. Ошибки в коде")


if __name__ == "__main__":
    asyncio.run(main())
