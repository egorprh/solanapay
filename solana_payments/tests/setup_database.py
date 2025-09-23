#!/usr/bin/env python3
"""
Скрипт для настройки базы данных MongoDB для Solana Payments

Создает необходимые коллекции и индексы, а также добавляет тестовые кошельки.
"""

import asyncio
import os
import motor.motor_asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_database():
    """Настройка базы данных MongoDB"""
    
    # Подключение к MongoDB
    mongo_url = os.environ.get("MONGODB_URL") or "mongodb://mongodb:27017"
    mongo_db = os.environ.get("MONGODB_DATABASE") or "solana_payments"
    logger.info(f"Connecting to MongoDB at {mongo_url}, db={mongo_db}")
    client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
    db = client[mongo_db]
    
    try:
        # Создание индексов для коллекции платежей
        logger.info("Creating indexes for payments collection...")
        await db.payments.create_index("payment_id", unique=True)
        await db.payments.create_index("status")
        await db.payments.create_index("created_at")
        await db.payments.create_index("payment_address")
        logger.info("✅ Payment indexes created")
        
        # Создание индексов для коллекции кошельков
        logger.info("Creating indexes for wallets collection...")
        await db.wallets.create_index("network", unique=True)
        logger.info("✅ Wallet indexes created")
        
        # Создание тестовых кошельков
        logger.info("Creating test wallets...")
        test_wallets = [
            "3PmrYZ9KD3GLLnmGjJYcuGmt3zq2BBG34JLUhoUv7ZSL",
            "2kDfwYtSYiG18WJiTpsBKzBqAhVvDNhJjwvjw3nVsNN8",
            "DppBmsoG5ciXsYMnMmdmGicGHepd36oZ6hwVysTTYyrk",
            "EpufTXUZmndCdMX5CSwLTPeWbEVvpbbjjQMYSS7TDxYM"
        ]
        
        # Логируем предоставленные кошельки
        for i, wallet_address in enumerate(test_wallets):
            logger.info(f"Using wallet {i+1}: {wallet_address}")
        
        # Сохранение кошельков в БД
        wallet_doc = {
            "network": "solana",
            "addresses": test_wallets,
            "created_at": "2024-01-01T00:00:00Z",
            "description": "Test wallets for development"
        }
        
        # Удаляем существующий документ если есть
        await db.wallets.delete_one({"network": "solana"})
        
        # Вставляем новый документ
        await db.wallets.insert_one(wallet_doc)
        logger.info("✅ Test wallets saved to database")
        
        # Проверка созданных данных
        wallet_count = await db.wallets.count_documents({"network": "solana"})
        logger.info(f"✅ Database setup complete. Wallets in database: {wallet_count}")
        
        # Вывод информации о кошельках
        wallet_doc = await db.wallets.find_one({"network": "solana"})
        if wallet_doc:
            logger.info(f"✅ Wallet pool contains {len(wallet_doc['addresses'])} addresses")
            logger.info("Provided wallet addresses:")
            for i, addr in enumerate(wallet_doc['addresses']):
                logger.info(f"  {i+1}. {addr}")
        
    except Exception as e:
        logger.error(f"❌ Error setting up database: {e}")
        raise
    finally:
        client.close()

if __name__ == "__main__":
    print("🚀 Setting up Solana Payments database...")
    asyncio.run(setup_database())
    print("✅ Database setup complete!")
