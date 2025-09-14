#!/usr/bin/env python3
"""
Настройка Solana Payments для работы с Devnet

Создает конфигурацию и тестовые данные для работы в Solana Devnet.
Включает настройку кошельков и проверку подключения к devnet.
"""

import asyncio
import motor.motor_asyncio
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_devnet_config():
    """Настройка конфигурации для devnet"""
    
    # Подключение к MongoDB
    client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["solana_payments"]
    
    try:
        logger.info("🔧 Setting up Devnet configuration...")
        
        # Создание индексов
        await db.payments.create_index("payment_id", unique=True)
        await db.payments.create_index("status")
        await db.payments.create_index("created_at")
        await db.wallets.create_index("network", unique=True)
        logger.info("✅ Database indexes created")
        
        # Создание devnet кошельков
        logger.info("🔑 Creating Devnet wallets...")
        devnet_wallets = [
            "7kFnAf3anAerYByZYEKAsPnz2eXwHFJWuZa4eV5r9wxT",
            "5sq5a9g1VNSzgVQRTsjP29iHi4eAezMw52KrJR5g53jg",
            "GJ8mMfgWm77L4uNDZvSaf2QhKn1hkgbNq3JZKLkvEx2H",
            "8xk2kwnxjVP3hx3Hsunra3yJMrHoRU4As7Q37QeHHJk9"
        ]
        
        # Логируем предоставленные кошельки
        for i, wallet_address in enumerate(devnet_wallets):
            logger.info(f"Using wallet {i+1}: {wallet_address}")
        
        # Сохранение кошельков
        wallet_doc = {
            "network": "solana",
            "addresses": devnet_wallets,
            "created_at": "2024-01-01T00:00:00Z",
            "description": "Devnet wallets for testing",
            "environment": "devnet"
        }
        
        # Удаляем существующий документ
        await db.wallets.delete_one({"network": "solana"})
        
        # Вставляем новый
        await db.wallets.insert_one(wallet_doc)
        logger.info("✅ Devnet wallets saved to database")
        
        # Проверка подключения к devnet
        logger.info("🌐 Testing Devnet connection...")
        solana_client = AsyncClient("https://api.devnet.solana.com")
        
        try:
            # Проверяем версию сети
            version = await solana_client.get_version()
            logger.info(f"✅ Devnet version: {version.value}")
            
            # Получаем последний слот
            slot = await solana_client.get_slot()
            logger.info(f"✅ Current slot: {slot}")
            
        except Exception as e:
            logger.error(f"❌ Devnet connection failed: {e}")
            raise
        finally:
            await solana_client.close()
        
        # Тест airdrop
        logger.info("💰 Testing airdrop functionality...")
        test_keypair = Keypair()
        test_address = str(test_keypair.pubkey())
        
        solana_client = AsyncClient("https://api.devnet.solana.com")
        try:
            airdrop_response = await solana_client.request_airdrop(
                test_keypair.pubkey(), 
                1 * 10**9  # 1 SOL
            )
            
            if airdrop_response.value:
                logger.info(f"✅ Airdrop test successful: {airdrop_response.value}")
                
                # Ждем подтверждения
                await asyncio.sleep(3)
                
                # Проверяем баланс
                balance_response = await solana_client.get_balance(test_keypair.public_key)
                balance_sol = balance_response.value / 10**9
                logger.info(f"✅ Test wallet balance: {balance_sol} SOL")
            else:
                logger.error("❌ Airdrop test failed")
                
        except Exception as e:
            logger.error(f"❌ Airdrop test error: {e}")
        finally:
            await solana_client.close()
        
        logger.info("✅ Devnet setup complete!")
        logger.info(f"📊 Using {len(devnet_wallets)} provided wallets")
        logger.info("🔗 Devnet RPC: https://api.devnet.solana.com")
        logger.info("🔍 Solscan Devnet: https://solscan.io/?cluster=devnet")
        
    except Exception as e:
        logger.error(f"❌ Devnet setup failed: {e}")
        raise
    finally:
        client.close()

if __name__ == "__main__":
    print("🚀 Setting up Solana Payments for Devnet...")
    asyncio.run(setup_devnet_config())
    print("✅ Devnet setup complete!")
    print("\n📋 Next steps:")
    print("1. Run: python test_devnet.py")
    print("2. Check the generated test report")
    print("3. View transactions in Solscan Devnet")
