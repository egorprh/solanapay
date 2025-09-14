#!/usr/bin/env python3
"""
Тестовый пример использования Solana Payments

Демонстрирует основные функции библиотеки:
- Создание платежа
- Проверка статуса
- Отмена платежа
"""

import asyncio
import uuid
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solana_payments import initialize, create_payment, get_payment_status, cancel_payment, cleanup

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_solana_payments():
    """Тестирование основных функций Solana Payments"""
    
    try:
        logger.info("🚀 Initializing Solana Payments...")
        await initialize()
        logger.info("✅ Initialization complete")
        
        # Тест 1: Создание платежа
        logger.info("\n📝 Test 1: Creating payment...")
        payment_id = str(uuid.uuid4())
        payment = await create_payment(payment_id, "sol")
        
        logger.info(f"✅ Payment created successfully!")
        logger.info(f"   Payment ID: {payment['payment_id']}")
        logger.info(f"   Token: {payment['token']}")
        logger.info(f"   Address: {payment['payment_address']}")
        logger.info(f"   Status: {payment['status']}")
        logger.info(f"   Initial Balance: {payment['initial_balance']} SOL")
        
        # Тест 2: Проверка статуса (должен быть pending)
        logger.info("\n🔍 Test 2: Checking payment status...")
        status = await get_payment_status(payment_id)
        logger.info(f"✅ Status check complete!")
        logger.info(f"   Status: {status['status']}")
        logger.info(f"   Updated: {status['updated_at']}")
        
        # Тест 3: Отмена платежа
        logger.info("\n❌ Test 3: Cancelling payment...")
        cancelled = await cancel_payment(payment_id)
        logger.info(f"✅ Payment cancelled successfully!")
        logger.info(f"   Status: {cancelled['status']}")
        logger.info(f"   Updated: {cancelled['updated_at']}")
        
        # Тест 4: Проверка после отмены
        logger.info("\n🔍 Test 4: Checking status after cancellation...")
        final_status = await get_payment_status(payment_id)
        logger.info(f"✅ Final status check complete!")
        logger.info(f"   Status: {final_status['status']}")
        
        logger.info("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise
    finally:
        logger.info("\n🧹 Cleaning up...")
        await cleanup()
        logger.info("✅ Cleanup complete")

async def test_multiple_payments():
    """Тест создания нескольких платежей"""
    
    try:
        logger.info("\n🔄 Testing multiple payments...")
        await initialize()
        
        # Создаем 3 платежа
        payments = []
        for i in range(3):
            payment_id = str(uuid.uuid4())
            token = ["sol", "usdc", "usdt"][i]
            
            payment = await create_payment(payment_id, token)
            payments.append(payment)
            
            logger.info(f"✅ Payment {i+1} created: {token.upper()} -> {payment['payment_address']}")
        
        # Проверяем статусы
        for i, payment in enumerate(payments):
            status = await get_payment_status(payment['payment_id'])
            logger.info(f"✅ Payment {i+1} status: {status['status']}")
        
        # Отменяем все платежи
        for i, payment in enumerate(payments):
            await cancel_payment(payment['payment_id'])
            logger.info(f"✅ Payment {i+1} cancelled")
        
        logger.info("🎉 Multiple payments test completed!")
        
    except Exception as e:
        logger.error(f"❌ Multiple payments test failed: {e}")
        raise
    finally:
        await cleanup()

async def main():
    """Главная функция для запуска тестов"""
    
    print("🧪 Solana Payments Test Suite")
    print("=" * 50)
    
    try:
        # Основные тесты
        await test_solana_payments()
        
        # Тест множественных платежей
        await test_multiple_payments()
        
        print("\n🎉 All tests passed successfully!")
        print("\n📋 Next steps:")
        print("1. Send real SOL to one of the generated addresses")
        print("2. Check the payment status to see if it's detected")
        print("3. Integrate the library into your application")
        
    except Exception as e:
        print(f"\n❌ Tests failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure MongoDB is running: brew services start mongodb-community")
        print("2. Make sure Redis is running: brew services start redis")
        print("3. Run setup_database.py to initialize the database")
        print("4. Check your internet connection for Solana RPC")

if __name__ == "__main__":
    asyncio.run(main())
