#!/usr/bin/env python3
"""
Тесты Solana Payments в Devnet

Создает реальные транзакции в Solana Devnet для проверки полного цикла работы:
1. Создание платежа
2. Отправка SOL на адрес платежа
3. Проверка обнаружения платежа
4. Генерация отчета с ссылками на Solscan

Требования:
- Подключение к Solana Devnet RPC
- Захардкоженный тестовый кошелек с SOL
"""

import asyncio
import uuid
import json
import logging
from datetime import datetime
from typing import Dict, List, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solana_payments import initialize, create_payment, get_payment_status, cancel_payment, cleanup, Config, get_payment_summary
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey as PublicKey
from solana.rpc.types import TxOpts
from solders.transaction import Transaction
from solders.system_program import transfer, TransferParams

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DevnetTester:
    """Класс для тестирования Solana Payments в Devnet"""
    
    def __init__(self):
        self.config = Config()
        # Используем Devnet RPC
        self.config.SOLANA_RPC_URL = "https://api.devnet.solana.com"
        self.config.SOLANA_COMMITMENT = "confirmed"
        
        self.test_results = []
        self.sender_keypair = None
        self.sender_address = None
        
    async def setup_test_wallet(self) -> None:
        """Настройка тестового кошелька для отправки SOL"""
        try:
            # Используем захардкоженный кошелек с SOL для тестирования
            private_key_hex = "57625c875c97f047a1a4c5fc22e998f63313b96242af9b43756eb8729eca287a"
            self.sender_address = "H6aLaK4cuFzqsDSHLKXYfyXJLtEpWpKS7BYbhf1Z3zLn"
            
            # Создаем Keypair из приватного ключа
            from solders.keypair import Keypair
            private_key_bytes = bytes.fromhex(private_key_hex)
            self.sender_keypair = Keypair.from_seed(private_key_bytes)
            
            logger.info(f"🔑 Using hardcoded test wallet: {self.sender_address}")
            
            # Проверяем баланс кошелька
            solana_client = AsyncClient(self.config.SOLANA_RPC_URL)
            
            logger.info("💰 Checking wallet balance...")
            balance_response = await solana_client.get_balance(self.sender_keypair.pubkey())
            balance_sol = round(balance_response.value / 10**9, 8)
            logger.info(f"💰 Wallet balance: {balance_sol} SOL")
            
            if balance_sol < 0.1:
                logger.warning("⚠️ Low balance! Make sure the wallet has enough SOL for testing.")
                raise Exception(f"Insufficient balance: {balance_sol} SOL")
            
            await solana_client.close()
            
        except Exception as e:
            logger.error(f"❌ Failed to setup test wallet: {e}")
            raise
    
    async def cleanup_locked_wallets(self) -> None:
        """Очистка всех заблокированных кошельков в Redis"""
        try:
            from solana_payments import SolanaPayments
            
            # Создаем временный экземпляр для доступа к Redis
            temp_payments = SolanaPayments()
            await temp_payments.initialize(self.config)
            
            # Получаем все заблокированные кошельки
            locked_keys = await temp_payments.redis_client.keys("occupied_wallet:solana:*")
            
            if locked_keys:
                logger.info(f"🔍 Found {len(locked_keys)} locked wallets")
                
                # Удаляем все заблокированные кошельки
                for key in locked_keys:
                    await temp_payments.redis_client.delete(key)
                    wallet_address = key.decode('utf-8').split(':')[-1]
                    logger.info(f"🔓 Released wallet: {wallet_address}")
                
                logger.info(f"✅ Released {len(locked_keys)} wallets")
            else:
                logger.info("✅ No locked wallets found")
            
            await temp_payments.cleanup()
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to cleanup locked wallets: {e}")
    
    async def check_and_fund_sender(self, required_amount: float = 0.5):
        """Проверка и пополнение баланса отправителя"""
        try:
            solana_client = AsyncClient(self.config.SOLANA_RPC_URL)
            sender_balance = await solana_client.get_balance(self.sender_keypair.pubkey())
            sender_balance_sol = round(sender_balance.value / 10**9, 8)
            
            logger.info(f"💰 Current sender balance: {sender_balance_sol:.8f} SOL")
            
            if sender_balance_sol < required_amount:
                logger.info(f"💸 Sender balance too low, requesting airdrop...")
                # Запрашиваем airdrop
                airdrop_amount = int(1.0 * 10**9)  # 1 SOL
                signature = await solana_client.request_airdrop(
                    self.sender_keypair.pubkey(), 
                    airdrop_amount
                )
                logger.info(f"✅ Airdrop requested: {signature}")
                
                # Ждем подтверждения
                await solana_client.confirm_transaction(signature)
                
                # Проверяем новый баланс
                new_balance = await solana_client.get_balance(self.sender_keypair.pubkey())
                new_balance_sol = round(new_balance.value / 10**9, 8)
                logger.info(f"💰 New sender balance: {new_balance_sol:.8f} SOL")
            else:
                logger.info(f"✅ Sender has sufficient balance: {sender_balance_sol:.8f} SOL")
                
        except Exception as e:
            logger.error(f"❌ Error checking/funding sender: {e}")
    
    async def send_sol_transaction(self, recipient_address: str, amount_sol: float) -> str:
        """
        Отправка реальной SOL транзакции
        
        Args:
            recipient_address: Адрес получателя
            amount_sol: Количество SOL для отправки
            
        Returns:
            Подпись транзакции
        """
        try:
            solana_client = AsyncClient(self.config.SOLANA_RPC_URL)
            
            # Конвертируем SOL в lamports
            amount_lamports = int(amount_sol * 10**9)
            
            # Проверяем баланс отправителя
            sender_balance = await solana_client.get_balance(self.sender_keypair.pubkey())
            sender_balance_sol = round(sender_balance.value / 10**9, 8)
            
            logger.info(f"💰 Sender balance: {sender_balance_sol:.8f} SOL")
            logger.info(f"📤 Sending {amount_sol} SOL to {recipient_address}")
            
            if sender_balance_sol < amount_sol:
                raise Exception(f"Insufficient balance: {sender_balance_sol:.8f} SOL < {amount_sol} SOL")
            
            # Создаем инструкцию перевода
            transfer_instruction = transfer(
                TransferParams(
                    from_pubkey=self.sender_keypair.pubkey(),
                    to_pubkey=PublicKey.from_string(recipient_address),
                    lamports=amount_lamports
                )
            )
            
            # Получаем последний блокхэш
            recent_blockhash = await solana_client.get_latest_blockhash()
            
            # Создаем транзакцию с правильным API для solders
            from solders.message import MessageV0
            from solders.transaction import VersionedTransaction
            
            # Создаем сообщение
            message = MessageV0.try_compile(
                payer=self.sender_keypair.pubkey(),
                instructions=[transfer_instruction],
                address_lookup_table_accounts=[],
                recent_blockhash=recent_blockhash.value.blockhash
            )
            
            # Создаем версионированную транзакцию
            transaction = VersionedTransaction(message, [self.sender_keypair])
            
            # Отправляем транзакцию
            response = await solana_client.send_transaction(
                transaction,
                opts=TxOpts(skip_preflight=False, preflight_commitment="confirmed")
            )
            
            signature = response.value
            logger.info(f"✅ Transaction sent: {signature}")
            
            # Ждем подтверждения
            logger.info("⏳ Waiting for confirmation...")
            await solana_client.confirm_transaction(signature, commitment="confirmed")
            
            await solana_client.close()
            
            return signature
            
        except Exception as e:
            logger.error(f"❌ Failed to send transaction: {e}")
            raise
    
    async def test_single_payment(self, test_name: str, amount_sol: float = 0.1) -> Dict[str, Any]:
        """
        Тест одного платежа
        
        Args:
            test_name: Название теста
            amount_sol: Количество SOL для отправки
            
        Returns:
            Результат теста
        """
        test_result = {
            "test_name": test_name,
            "start_time": datetime.now().isoformat(),
            "success": False,
            "error": None,
            "payment_id": None,
            "payment_address": None,
            "transaction_signature": None,
            "solscan_url": None,
            "payment_data": None,
            "status_checks": []
        }
        
        try:
            logger.info(f"\n🧪 Starting test: {test_name}")
            
            # 0. Проверка и пополнение баланса отправителя
            await self.check_and_fund_sender(required_amount=0.2)
            
            # 1. Создание платежа
            payment_id = str(uuid.uuid4())
            logger.info(f"📝 Creating payment: {payment_id}")
            
            payment = await create_payment(payment_id, "sol")
            test_result["payment_id"] = payment_id
            test_result["payment_address"] = payment["payment_address"]
            
            logger.info(f"✅ Payment created: {payment['payment_address']}")
            
            # 2. Проверка начального статуса
            initial_status = await get_payment_status(payment_id)
            test_result["status_checks"].append({
                "check": "initial_status",
                "status": initial_status["status"],
                "timestamp": datetime.now().isoformat()
            })
            
            # 3. Отправка SOL
            logger.info(f"📤 Sending {amount_sol} SOL...")
            signature = await self.send_sol_transaction(payment["payment_address"], amount_sol)
            test_result["transaction_signature"] = signature
            test_result["solscan_url"] = f"https://solscan.io/tx/{signature}?cluster=devnet"
            
            # 4. Проверка статуса после отправки (несколько попыток)
            for attempt in range(5):
                await asyncio.sleep(3)  # Ждем 3 секунды между проверками
                
                status = await get_payment_status(payment_id)
                test_result["status_checks"].append({
                    "check": f"after_transaction_attempt_{attempt + 1}",
                    "status": status["status"],
                    "payment_amount": status.get("payment_amount"),
                    "outcome_amount": status.get("outcome_amount"),
                    "timestamp": datetime.now().isoformat()
                })
                
                if status["status"] == "paid":
                    logger.info(f"✅ Payment detected! Amount: {status.get('payment_amount')} SOL")
                    test_result["payment_data"] = status
                    test_result["success"] = True
                    break
                else:
                    logger.info(f"⏳ Payment still pending... (attempt {attempt + 1}/5)")
            
            if not test_result["success"]:
                test_result["error"] = "Payment not detected after 5 attempts"
                logger.error("❌ Payment was not detected")
            
        except Exception as e:
            test_result["error"] = str(e)
            logger.error(f"❌ Test failed: {e}")
        
        test_result["end_time"] = datetime.now().isoformat()
        return test_result
    
    async def test_multiple_payments(self) -> List[Dict[str, Any]]:
        """Тест множественных платежей"""
        results = []
        
        # Тест 1: Малый платеж
        result1 = await self.test_single_payment("Small Payment Test", 0.01)
        results.append(result1)
        
        # Небольшая пауза между тестами
        await asyncio.sleep(2)
        
        # Тест 2: Средний платеж
        result2 = await self.test_single_payment("Medium Payment Test", 0.05)
        results.append(result2)
        
        # Пауза
        await asyncio.sleep(2)
        
        # Тест 3: Большой платеж
        result3 = await self.test_single_payment("Large Payment Test", 0.1)
        results.append(result3)
        
        return results
    
    async def test_partial_payments(self) -> List[Dict[str, Any]]:
        """Тест частичных платежей"""
        results = []
        
        # Тест 1: Частичный платеж (30% от ожидаемой суммы)
        result1 = await self.test_partial_payment("Partial Payment Test (30%)", 0.1, 0.03)
        results.append(result1)
        
        # Пауза между тестами
        await asyncio.sleep(3)
        
        # Тест 2: Завершение частичного платежа (50% + 50%)
        result2 = await self.test_complete_partial_payment("Complete Partial Payment Test", 0.1, 0.05, 0.05)
        results.append(result2)
        
        # Пауза
        await asyncio.sleep(3)
        
        # Тест 3: Переплата (120% от ожидаемой суммы)
        result3 = await self.test_overpayment("Overpayment Test (120%)", 0.1, 0.12)
        results.append(result3)
        
        # Пауза
        await asyncio.sleep(3)
        
        # Тест 4: Отмена частично оплаченного платежа
        result4 = await self.test_partial_payment_cancellation("Partial Payment Cancellation Test", 0.1, 0.04)
        results.append(result4)
        
        # Пауза
        await asyncio.sleep(3)
        
        # Тест 5: Частичный платеж с проверкой остатка
        result5 = await self.test_partial_payment_with_remaining_balance("Partial Payment with Remaining Balance Test", 0.1, 0.07)
        results.append(result5)
        
        # Пауза
        await asyncio.sleep(3)
        
        # Тест 6: Частичный платеж с тремя транзакциями
        result6 = await self.test_partial_payment_with_three_installments("Three-Installment Partial Payment Test", 0.1, 0.03, 0.04, 0.03)
        results.append(result6)
        
        return results
    
    async def test_cancellation(self) -> Dict[str, Any]:
        """Тест отмены платежа"""
        test_result = {
            "test_name": "Payment Cancellation Test",
            "start_time": datetime.now().isoformat(),
            "success": False,
            "error": None,
            "payment_id": None,
            "cancellation_result": None
        }
        
        try:
            logger.info("\n🧪 Starting cancellation test...")
            
            # Создаем платеж
            payment_id = str(uuid.uuid4())
            payment = await create_payment(payment_id, "sol")
            test_result["payment_id"] = payment_id
            
            logger.info(f"✅ Payment created: {payment['payment_address']}")
            
            # Отменяем платеж
            cancelled = await cancel_payment(payment_id)
            test_result["cancellation_result"] = cancelled
            
            if cancelled["status"] == "cancelled":
                test_result["success"] = True
                logger.info("✅ Payment cancelled successfully")
            else:
                test_result["error"] = "Cancellation failed"
                logger.error("❌ Payment cancellation failed")
            
        except Exception as e:
            test_result["error"] = str(e)
            logger.error(f"❌ Cancellation test failed: {e}")
        
        test_result["end_time"] = datetime.now().isoformat()
        return test_result
    
    async def test_partial_payment(self, test_name: str, expected_amount: float, partial_amount: float) -> Dict[str, Any]:
        """
        Тест частичного платежа
        
        Args:
            test_name: Название теста
            expected_amount: Ожидаемая сумма платежа
            partial_amount: Сумма частичного платежа
            
        Returns:
            Результат теста
        """
        test_result = {
            "test_name": test_name,
            "start_time": datetime.now().isoformat(),
            "success": False,
            "error": None,
            "payment_id": None,
            "payment_address": None,
            "transaction_signature": None,
            "solscan_url": None,
            "payment_data": None,
            "status_checks": [],
            "expected_amount": expected_amount,
            "partial_amount": partial_amount
        }
        
        try:
            logger.info(f"\n🧪 Starting partial payment test: {test_name}")
            logger.info(f"Expected: {expected_amount} SOL, Partial: {partial_amount} SOL")
            
            # 0. Проверка и пополнение баланса отправителя
            await self.check_and_fund_sender(required_amount=0.2)
            
            # 1. Создание платежа с ожидаемой суммой
            payment_id = str(uuid.uuid4())
            logger.info(f"📝 Creating payment: {payment_id}")
            
            payment = await create_payment(payment_id, "sol", expected_amount=expected_amount)
            test_result["payment_id"] = payment_id
            test_result["payment_address"] = payment["payment_address"]
            
            logger.info(f"✅ Payment created: {payment['payment_address']}")
            logger.info(f"Expected amount: {payment['expected_amount']} SOL")
            
            # 2. Проверка начального статуса
            initial_status = await get_payment_status(payment_id)
            test_result["status_checks"].append({
                "check": "initial_status",
                "status": initial_status["status"],
                "expected_amount": initial_status.get("expected_amount"),
                "paid_amount": initial_status.get("paid_amount", 0),
                "remaining_amount": initial_status.get("remaining_amount"),
                "timestamp": datetime.now().isoformat()
            })
            
            # 3. Отправка частичного платежа
            logger.info(f"📤 Sending partial payment: {partial_amount} SOL...")
            signature = await self.send_sol_transaction(payment["payment_address"], partial_amount)
            test_result["transaction_signature"] = signature
            test_result["solscan_url"] = f"https://solscan.io/tx/{signature}?cluster=devnet"
            
            # 4. Проверка статуса после частичного платежа
            for attempt in range(5):
                await asyncio.sleep(3)  # Ждем 3 секунды между проверками
                
                status = await get_payment_status(payment_id)
                test_result["status_checks"].append({
                    "check": f"after_partial_payment_attempt_{attempt + 1}",
                    "status": status["status"],
                    "expected_amount": status.get("expected_amount"),
                    "paid_amount": status.get("paid_amount", 0),
                    "remaining_amount": status.get("remaining_amount"),
                    "outcome_amount": status.get("outcome_amount"),
                    "timestamp": datetime.now().isoformat()
                })
                
                if status["status"] == "partial":
                    logger.info(f"✅ Partial payment detected! Paid: {status.get('paid_amount')} SOL, Remaining: {status.get('remaining_amount')} SOL")
                    test_result["payment_data"] = status
                    test_result["success"] = True
                    
                    # Освобождаем кошелек для частичного платежа в тестах
                    logger.info(f"🔓 Releasing wallet for partial payment test...")
                    await cancel_payment(payment_id)
                    break
                else:
                    logger.info(f"⏳ Payment status: {status['status']}... (attempt {attempt + 1}/5)")
            
            if not test_result["success"]:
                test_result["error"] = f"Partial payment not detected. Status: {status['status']}"
                logger.error("❌ Partial payment was not detected")
            
        except Exception as e:
            test_result["error"] = str(e)
            logger.error(f"❌ Partial payment test failed: {e}")
            
            # Освобождаем кошелек в случае исключения
            if test_result.get("payment_id"):
                logger.info(f"🔓 Releasing wallet due to exception...")
                try:
                    await cancel_payment(test_result["payment_id"])
                except Exception as release_error:
                    logger.warning(f"Failed to release wallet: {release_error}")
        
        test_result["end_time"] = datetime.now().isoformat()
        return test_result
    
    async def test_complete_partial_payment(self, test_name: str, expected_amount: float, first_partial: float, second_partial: float) -> Dict[str, Any]:
        """
        Тест завершения частичного платежа (два платежа)
        
        Args:
            test_name: Название теста
            expected_amount: Ожидаемая сумма платежа
            first_partial: Первая частичная сумма
            second_partial: Вторая частичная сумма
            
        Returns:
            Результат теста
        """
        test_result = {
            "test_name": test_name,
            "start_time": datetime.now().isoformat(),
            "success": False,
            "error": None,
            "payment_id": None,
            "payment_address": None,
            "first_transaction_signature": None,
            "second_transaction_signature": None,
            "first_solscan_url": None,
            "second_solscan_url": None,
            "payment_data": None,
            "status_checks": [],
            "expected_amount": expected_amount,
            "first_partial": first_partial,
            "second_partial": second_partial
        }
        
        try:
            logger.info(f"\n🧪 Starting complete partial payment test: {test_name}")
            logger.info(f"Expected: {expected_amount} SOL, First: {first_partial} SOL, Second: {second_partial} SOL")
            
            # 1. Создание платежа с ожидаемой суммой
            payment_id = str(uuid.uuid4())
            logger.info(f"📝 Creating payment: {payment_id}")
            
            payment = await create_payment(payment_id, "sol", expected_amount=expected_amount)
            test_result["payment_id"] = payment_id
            test_result["payment_address"] = payment["payment_address"]
            
            logger.info(f"✅ Payment created: {payment['payment_address']}")
            
            # 2. Первый частичный платеж
            logger.info(f"📤 Sending first partial payment: {first_partial} SOL...")
            first_signature = await self.send_sol_transaction(payment["payment_address"], first_partial)
            test_result["first_transaction_signature"] = first_signature
            test_result["first_solscan_url"] = f"https://solscan.io/tx/{first_signature}?cluster=devnet"
            
            # 3. Проверка статуса после первого платежа
            await asyncio.sleep(5)  # Ждем обработки
            status_after_first = await get_payment_status(payment_id)
            test_result["status_checks"].append({
                "check": "after_first_partial",
                "status": status_after_first["status"],
                "paid_amount": status_after_first.get("paid_amount", 0),
                "remaining_amount": status_after_first.get("remaining_amount"),
                "timestamp": datetime.now().isoformat()
            })
            
            if status_after_first["status"] != "partial":
                test_result["error"] = f"Expected 'partial' status after first payment, got '{status_after_first['status']}'"
                logger.error(f"❌ Unexpected status after first payment: {status_after_first['status']}")
                return test_result
            
            logger.info(f"✅ First partial payment confirmed: {status_after_first.get('paid_amount')} SOL paid")
            
            # 4. Второй частичный платеж
            logger.info(f"📤 Sending second partial payment: {second_partial} SOL...")
            second_signature = await self.send_sol_transaction(payment["payment_address"], second_partial)
            test_result["second_transaction_signature"] = second_signature
            test_result["second_solscan_url"] = f"https://solscan.io/tx/{second_signature}?cluster=devnet"
            
            logger.info(f"✅ Second transaction sent: {second_signature}")
            
            # 5. Проверка финального статуса
            for attempt in range(8):  # Увеличиваем количество попыток
                await asyncio.sleep(5)  # Увеличиваем время ожидания
                
                final_status = await get_payment_status(payment_id)
                test_result["status_checks"].append({
                    "check": f"after_second_partial_attempt_{attempt + 1}",
                    "status": final_status["status"],
                    "paid_amount": final_status.get("paid_amount", 0),
                    "remaining_amount": final_status.get("remaining_amount"),
                    "outcome_amount": final_status.get("outcome_amount"),
                    "timestamp": datetime.now().isoformat()
                })
                
                if final_status["status"] in ["paid", "overpaid"]:
                    logger.info(f"✅ Payment completed! Status: {final_status['status']}, Total paid: {final_status.get('paid_amount')} SOL")
                    test_result["payment_data"] = final_status
                    test_result["success"] = True
                    break
                else:
                    logger.info(f"⏳ Payment status: {final_status['status']}... (attempt {attempt + 1}/8)")
                    logger.info(f"   Paid: {final_status.get('paid_amount', 0)} SOL, Remaining: {final_status.get('remaining_amount', 0)} SOL")
            
            if not test_result["success"]:
                test_result["error"] = f"Payment not completed. Final status: {final_status['status']}"
                logger.error("❌ Payment was not completed")
                
                # Освобождаем кошелек в случае неудачи
                logger.info(f"🔓 Releasing wallet due to test failure...")
                try:
                    await cancel_payment(payment_id)
                except Exception as e:
                    logger.warning(f"Failed to release wallet: {e}")
            
        except Exception as e:
            test_result["error"] = str(e)
            logger.error(f"❌ Complete partial payment test failed: {e}")
            
            # Освобождаем кошелек в случае исключения
            if test_result.get("payment_id"):
                logger.info(f"🔓 Releasing wallet due to exception...")
                try:
                    await cancel_payment(test_result["payment_id"])
                except Exception as release_error:
                    logger.warning(f"Failed to release wallet: {release_error}")
        
        test_result["end_time"] = datetime.now().isoformat()
        return test_result
    
    async def test_partial_payment_with_three_installments(self, test_name: str, expected_amount: float, first_partial: float, second_partial: float, third_partial: float) -> Dict[str, Any]:
        """
        Тест частичного платежа с тремя транзакциями
        
        Args:
            test_name: Название теста
            expected_amount: Ожидаемая сумма платежа
            first_partial: Первая частичная сумма
            second_partial: Вторая частичная сумма
            third_partial: Третья частичная сумма
            
        Returns:
            Результат теста
        """
        test_result = {
            "test_name": test_name,
            "start_time": datetime.now().isoformat(),
            "success": False,
            "error": None,
            "payment_id": None,
            "payment_address": None,
            "first_transaction_signature": None,
            "second_transaction_signature": None,
            "third_transaction_signature": None,
            "first_solscan_url": None,
            "second_solscan_url": None,
            "third_solscan_url": None,
            "payment_data": None,
            "status_checks": [],
            "expected_amount": expected_amount,
            "first_partial": first_partial,
            "second_partial": second_partial,
            "third_partial": third_partial
        }
        
        try:
            logger.info(f"\n🧪 Starting three-installment partial payment test: {test_name}")
            logger.info(f"Expected: {expected_amount} SOL, First: {first_partial} SOL, Second: {second_partial} SOL, Third: {third_partial} SOL")
            
            # 0. Проверка и пополнение баланса отправителя
            await self.check_and_fund_sender(required_amount=0.3)
            
            # 1. Создание платежа с ожидаемой суммой
            payment_id = str(uuid.uuid4())
            logger.info(f"📝 Creating payment: {payment_id}")
            
            payment = await create_payment(payment_id, "sol", expected_amount=expected_amount)
            test_result["payment_id"] = payment_id
            test_result["payment_address"] = payment["payment_address"]
            
            logger.info(f"✅ Payment created: {payment['payment_address']}")
            
            # 2. Первый частичный платеж
            logger.info(f"📤 Sending first partial payment: {first_partial} SOL...")
            first_signature = await self.send_sol_transaction(payment["payment_address"], first_partial)
            test_result["first_transaction_signature"] = first_signature
            test_result["first_solscan_url"] = f"https://solscan.io/tx/{first_signature}?cluster=devnet"
            
            # 3. Проверка статуса после первого платежа
            await asyncio.sleep(5)
            status_after_first = await get_payment_status(payment_id)
            test_result["status_checks"].append({
                "check": "after_first_partial",
                "status": status_after_first["status"],
                "paid_amount": status_after_first.get("paid_amount", 0),
                "remaining_amount": status_after_first.get("remaining_amount"),
                "timestamp": datetime.now().isoformat()
            })
            
            if status_after_first["status"] != "partial":
                test_result["error"] = f"Expected 'partial' status after first payment, got '{status_after_first['status']}'"
                logger.error(f"❌ Unexpected status after first payment: {status_after_first['status']}")
                return test_result
            
            logger.info(f"✅ First partial payment confirmed: {status_after_first.get('paid_amount')} SOL paid")
            
            # 4. Второй частичный платеж
            logger.info(f"📤 Sending second partial payment: {second_partial} SOL...")
            second_signature = await self.send_sol_transaction(payment["payment_address"], second_partial)
            test_result["second_transaction_signature"] = second_signature
            test_result["second_solscan_url"] = f"https://solscan.io/tx/{second_signature}?cluster=devnet"
            
            # 5. Проверка статуса после второго платежа
            await asyncio.sleep(5)
            status_after_second = await get_payment_status(payment_id)
            test_result["status_checks"].append({
                "check": "after_second_partial",
                "status": status_after_second["status"],
                "paid_amount": status_after_second.get("paid_amount", 0),
                "remaining_amount": status_after_second.get("remaining_amount"),
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"✅ Second partial payment confirmed: {status_after_second.get('paid_amount')} SOL paid")
            
            # 6. Третий частичный платеж
            logger.info(f"📤 Sending third partial payment: {third_partial} SOL...")
            third_signature = await self.send_sol_transaction(payment["payment_address"], third_partial)
            test_result["third_transaction_signature"] = third_signature
            test_result["third_solscan_url"] = f"https://solscan.io/tx/{third_signature}?cluster=devnet"
            
            # 7. Проверка финального статуса
            for attempt in range(8):
                await asyncio.sleep(5)
                
                final_status = await get_payment_status(payment_id)
                test_result["status_checks"].append({
                    "check": f"after_third_partial_attempt_{attempt + 1}",
                    "status": final_status["status"],
                    "paid_amount": final_status.get("paid_amount", 0),
                    "remaining_amount": final_status.get("remaining_amount"),
                    "outcome_amount": final_status.get("outcome_amount"),
                    "timestamp": datetime.now().isoformat()
                })
                
                if final_status["status"] in ["paid", "overpaid"]:
                    logger.info(f"✅ Payment completed! Status: {final_status['status']}, Total paid: {final_status.get('paid_amount')} SOL")
                    test_result["payment_data"] = final_status
                    test_result["success"] = True
                    break
                else:
                    logger.info(f"⏳ Payment status: {final_status['status']}... (attempt {attempt + 1}/8)")
                    logger.info(f"   Paid: {final_status.get('paid_amount', 0)} SOL, Remaining: {final_status.get('remaining_amount', 0)} SOL")
            
            if not test_result["success"]:
                test_result["error"] = f"Payment not completed. Final status: {final_status['status']}"
                logger.error("❌ Payment was not completed")
                
                # Освобождаем кошелек в случае неудачи
                logger.info(f"🔓 Releasing wallet due to test failure...")
                try:
                    await cancel_payment(payment_id)
                except Exception as e:
                    logger.warning(f"Failed to release wallet: {e}")
            
        except Exception as e:
            test_result["error"] = str(e)
            logger.error(f"❌ Three-installment partial payment test failed: {e}")
            
            # Освобождаем кошелек в случае исключения
            if test_result.get("payment_id"):
                logger.info(f"🔓 Releasing wallet due to exception...")
                try:
                    await cancel_payment(test_result["payment_id"])
                except Exception as release_error:
                    logger.warning(f"Failed to release wallet: {release_error}")
        
        test_result["end_time"] = datetime.now().isoformat()
        return test_result
    
    async def test_partial_payment_with_remaining_balance(self, test_name: str, expected_amount: float, partial_amount: float) -> Dict[str, Any]:
        """
        Тест частичного платежа с проверкой остатка
        
        Args:
            test_name: Название теста
            expected_amount: Ожидаемая сумма платежа
            partial_amount: Сумма частичного платежа
            
        Returns:
            Результат теста
        """
        test_result = {
            "test_name": test_name,
            "start_time": datetime.now().isoformat(),
            "success": False,
            "error": None,
            "payment_id": None,
            "payment_address": None,
            "transaction_signature": None,
            "solscan_url": None,
            "payment_data": None,
            "status_checks": [],
            "expected_amount": expected_amount,
            "partial_amount": partial_amount,
            "remaining_amount": round(expected_amount - partial_amount, 8)
        }
        
        try:
            logger.info(f"\n🧪 Starting partial payment with remaining balance test: {test_name}")
            logger.info(f"Expected: {expected_amount} SOL, Partial: {partial_amount} SOL, Remaining: {test_result['remaining_amount']} SOL")
            
            # 0. Проверка и пополнение баланса отправителя
            await self.check_and_fund_sender(required_amount=0.2)
            
            # 1. Создание платежа с ожидаемой суммой
            payment_id = str(uuid.uuid4())
            logger.info(f"📝 Creating payment: {payment_id}")
            
            payment = await create_payment(payment_id, "sol", expected_amount=expected_amount)
            test_result["payment_id"] = payment_id
            test_result["payment_address"] = payment["payment_address"]
            
            logger.info(f"✅ Payment created: {payment['payment_address']}")
            
            # 2. Отправка частичного платежа
            logger.info(f"📤 Sending partial payment: {partial_amount} SOL...")
            signature = await self.send_sol_transaction(payment["payment_address"], partial_amount)
            test_result["transaction_signature"] = signature
            test_result["solscan_url"] = f"https://solscan.io/tx/{signature}?cluster=devnet"
            
            # 3. Проверка статуса после частичного платежа
            for attempt in range(5):
                await asyncio.sleep(3)
                
                status = await get_payment_status(payment_id)
                test_result["status_checks"].append({
                    "check": f"after_partial_payment_attempt_{attempt + 1}",
                    "status": status["status"],
                    "expected_amount": status.get("expected_amount"),
                    "paid_amount": status.get("paid_amount", 0),
                    "remaining_amount": status.get("remaining_amount"),
                    "outcome_amount": status.get("outcome_amount"),
                    "timestamp": datetime.now().isoformat()
                })
                
                if status["status"] == "partial":
                    # Проверяем корректность расчетов
                    paid_amount = status.get("paid_amount", 0)
                    remaining_amount = status.get("remaining_amount", 0)
                    expected_remaining = round(expected_amount - paid_amount, 8)
                    
                    if abs(remaining_amount - expected_remaining) < 0.00000001:  # Учитываем погрешность с округлением
                        logger.info(f"✅ Partial payment detected with correct calculations!")
                        logger.info(f"   Paid: {paid_amount} SOL, Remaining: {remaining_amount} SOL")
                        test_result["payment_data"] = status
                        test_result["success"] = True
                        
                        # Освобождаем кошелек для частичного платежа в тестах
                        logger.info(f"🔓 Releasing wallet for partial payment test...")
                        await cancel_payment(payment_id)
                        break
                    else:
                        logger.warning(f"⚠️ Calculation mismatch: expected remaining {expected_remaining}, got {remaining_amount}")
                        test_result["error"] = f"Calculation mismatch: expected remaining {expected_remaining}, got {remaining_amount}"
                        break
                else:
                    logger.info(f"⏳ Payment status: {status['status']}... (attempt {attempt + 1}/5)")
            
            if not test_result["success"] and not test_result.get("error"):
                test_result["error"] = f"Partial payment not detected. Status: {status['status']}"
                logger.error("❌ Partial payment was not detected")
            
        except Exception as e:
            test_result["error"] = str(e)
            logger.error(f"❌ Partial payment with remaining balance test failed: {e}")
            
            # Освобождаем кошелек в случае исключения
            if test_result.get("payment_id"):
                logger.info(f"🔓 Releasing wallet due to exception...")
                try:
                    await cancel_payment(test_result["payment_id"])
                except Exception as release_error:
                    logger.warning(f"Failed to release wallet: {release_error}")
        
        test_result["end_time"] = datetime.now().isoformat()
        return test_result
    
    async def test_overpayment(self, test_name: str, expected_amount: float, overpayment_amount: float) -> Dict[str, Any]:
        """
        Тест переплаты
        
        Args:
            test_name: Название теста
            expected_amount: Ожидаемая сумма платежа
            overpayment_amount: Сумма переплаты
            
        Returns:
            Результат теста
        """
        test_result = {
            "test_name": test_name,
            "start_time": datetime.now().isoformat(),
            "success": False,
            "error": None,
            "payment_id": None,
            "payment_address": None,
            "transaction_signature": None,
            "solscan_url": None,
            "payment_data": None,
            "status_checks": [],
            "expected_amount": expected_amount,
            "overpayment_amount": overpayment_amount
        }
        
        try:
            logger.info(f"\n🧪 Starting overpayment test: {test_name}")
            logger.info(f"Expected: {expected_amount} SOL, Overpayment: {overpayment_amount} SOL")
            
            # 1. Создание платежа с ожидаемой суммой
            payment_id = str(uuid.uuid4())
            logger.info(f"📝 Creating payment: {payment_id}")
            
            payment = await create_payment(payment_id, "sol", expected_amount=expected_amount)
            test_result["payment_id"] = payment_id
            test_result["payment_address"] = payment["payment_address"]
            
            logger.info(f"✅ Payment created: {payment['payment_address']}")
            
            # 2. Отправка переплаты
            logger.info(f"📤 Sending overpayment: {overpayment_amount} SOL...")
            signature = await self.send_sol_transaction(payment["payment_address"], overpayment_amount)
            test_result["transaction_signature"] = signature
            test_result["solscan_url"] = f"https://solscan.io/tx/{signature}?cluster=devnet"
            
            # 3. Проверка статуса после переплаты
            for attempt in range(5):
                await asyncio.sleep(3)
                
                status = await get_payment_status(payment_id)
                test_result["status_checks"].append({
                    "check": f"after_overpayment_attempt_{attempt + 1}",
                    "status": status["status"],
                    "expected_amount": status.get("expected_amount"),
                    "paid_amount": status.get("paid_amount", 0),
                    "remaining_amount": status.get("remaining_amount"),
                    "outcome_amount": status.get("outcome_amount"),
                    "timestamp": datetime.now().isoformat()
                })
                
                if status["status"] == "overpaid":
                    overpaid_amount = status.get("paid_amount", 0) - status.get("expected_amount", 0)
                    logger.info(f"✅ Overpayment detected! Paid: {status.get('paid_amount')} SOL, Overpaid: {overpaid_amount} SOL")
                    test_result["payment_data"] = status
                    test_result["success"] = True
                    break
                elif status["status"] == "paid":
                    logger.info(f"✅ Payment completed (exact amount): {status.get('paid_amount')} SOL")
                    test_result["payment_data"] = status
                    test_result["success"] = True
                    break
                else:
                    logger.info(f"⏳ Payment status: {status['status']}... (attempt {attempt + 1}/5)")
            
            if not test_result["success"]:
                test_result["error"] = f"Overpayment not detected. Status: {status['status']}"
                logger.error("❌ Overpayment was not detected")
                
                # Освобождаем кошелек в случае неудачи
                logger.info(f"🔓 Releasing wallet due to test failure...")
                try:
                    await cancel_payment(payment_id)
                except Exception as e:
                    logger.warning(f"Failed to release wallet: {e}")
            
        except Exception as e:
            test_result["error"] = str(e)
            logger.error(f"❌ Overpayment test failed: {e}")
            
            # Освобождаем кошелек в случае исключения
            if test_result.get("payment_id"):
                logger.info(f"🔓 Releasing wallet due to exception...")
                try:
                    await cancel_payment(test_result["payment_id"])
                except Exception as release_error:
                    logger.warning(f"Failed to release wallet: {release_error}")
        
        test_result["end_time"] = datetime.now().isoformat()
        return test_result
    
    async def test_partial_payment_cancellation(self, test_name: str, expected_amount: float, partial_amount: float) -> Dict[str, Any]:
        """
        Тест отмены частично оплаченного платежа
        
        Args:
            test_name: Название теста
            expected_amount: Ожидаемая сумма платежа
            partial_amount: Сумма частичного платежа
            
        Returns:
            Результат теста
        """
        test_result = {
            "test_name": test_name,
            "start_time": datetime.now().isoformat(),
            "success": False,
            "error": None,
            "payment_id": None,
            "payment_address": None,
            "transaction_signature": None,
            "solscan_url": None,
            "cancellation_result": None,
            "status_checks": [],
            "expected_amount": expected_amount,
            "partial_amount": partial_amount
        }
        
        try:
            logger.info(f"\n🧪 Starting partial payment cancellation test: {test_name}")
            
            # 0. Проверка и пополнение баланса отправителя
            await self.check_and_fund_sender(required_amount=0.2)
            
            # 1. Создание платежа с ожидаемой суммой
            payment_id = str(uuid.uuid4())
            logger.info(f"📝 Creating payment: {payment_id}")
            
            payment = await create_payment(payment_id, "sol", expected_amount=expected_amount)
            test_result["payment_id"] = payment_id
            test_result["payment_address"] = payment["payment_address"]
            
            logger.info(f"✅ Payment created: {payment['payment_address']}")
            
            # 2. Отправка частичного платежа
            logger.info(f"📤 Sending partial payment: {partial_amount} SOL...")
            signature = await self.send_sol_transaction(payment["payment_address"], partial_amount)
            test_result["transaction_signature"] = signature
            test_result["solscan_url"] = f"https://solscan.io/tx/{signature}?cluster=devnet"
            
            # 3. Проверка статуса после частичного платежа
            await asyncio.sleep(5)
            status_after_payment = await get_payment_status(payment_id)
            test_result["status_checks"].append({
                "check": "after_partial_payment",
                "status": status_after_payment["status"],
                "paid_amount": status_after_payment.get("paid_amount", 0),
                "remaining_amount": status_after_payment.get("remaining_amount"),
                "timestamp": datetime.now().isoformat()
            })
            
            if status_after_payment["status"] != "partial":
                test_result["error"] = f"Expected 'partial' status, got '{status_after_payment['status']}'"
                logger.error(f"❌ Unexpected status: {status_after_payment['status']}")
                return test_result
            
            logger.info(f"✅ Partial payment confirmed: {status_after_payment.get('paid_amount')} SOL paid")
            
            # 4. Отмена платежа
            logger.info(f"🚫 Cancelling partial payment...")
            cancelled = await cancel_payment(payment_id)
            test_result["cancellation_result"] = cancelled
            
            if cancelled["status"] == "cancelled":
                test_result["success"] = True
                logger.info("✅ Partial payment cancelled successfully")
            else:
                test_result["error"] = f"Cancellation failed. Status: {cancelled['status']}"
                logger.error(f"❌ Cancellation failed: {cancelled['status']}")
            
        except Exception as e:
            test_result["error"] = str(e)
            logger.error(f"❌ Partial payment cancellation test failed: {e}")
            
            # Освобождаем кошелек в случае исключения
            if test_result.get("payment_id"):
                logger.info(f"🔓 Releasing wallet due to exception...")
                try:
                    await cancel_payment(test_result["payment_id"])
                except Exception as release_error:
                    logger.warning(f"Failed to release wallet: {release_error}")
        
        test_result["end_time"] = datetime.now().isoformat()
        return test_result
    
    def generate_report(self, results: List[Dict[str, Any]]) -> str:
        """Генерация отчета о тестах"""
        
        report = []
        report.append("# 🧪 Solana Payments Devnet Test Report")
        report.append(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Сеть:** Solana Devnet")
        report.append(f"**RPC:** {self.config.SOLANA_RPC_URL}")
        report.append("")
        
        # Статистика
        total_tests = len(results)
        successful_tests = sum(1 for r in results if r.get("success", False))
        failed_tests = total_tests - successful_tests
        
        report.append("## 📊 Статистика тестов")
        report.append(f"- **Всего тестов:** {total_tests}")
        report.append(f"- **Успешных:** {successful_tests}")
        report.append(f"- **Неудачных:** {failed_tests}")
        report.append(f"- **Успешность:** {(successful_tests/total_tests*100):.1f}%")
        report.append("")
        
        # Детальные результаты
        report.append("## 🔍 Детальные результаты")
        report.append("")
        
        for i, result in enumerate(results, 1):
            status_emoji = "✅" if result.get("success", False) else "❌"
            report.append(f"### {i}. {status_emoji} {result['test_name']}")
            report.append("")
            
            if result.get("success", False):
                report.append("**Статус:** Успешно")
                if result.get("payment_data"):
                    payment_data = result["payment_data"]
                    report.append(f"- **Получено:** {payment_data.get('payment_amount', 'N/A')} SOL")
                    report.append(f"- **Эквивалент:** ${payment_data.get('outcome_amount', 'N/A')}")
                    
                    # Дополнительная информация для частичных платежей
                    if result.get("expected_amount"):
                        report.append(f"- **Ожидаемая сумма:** {result['expected_amount']} SOL")
                    if payment_data.get("paid_amount") is not None:
                        report.append(f"- **Оплачено:** {payment_data.get('paid_amount')} SOL")
                    if payment_data.get("remaining_amount") is not None:
                        report.append(f"- **Осталось:** {payment_data.get('remaining_amount')} SOL")
            else:
                report.append("**Статус:** Неудачно")
                if result.get("error"):
                    report.append(f"- **Ошибка:** {result['error']}")
            
            if result.get("payment_id"):
                report.append(f"- **Payment ID:** `{result['payment_id']}`")
            
            if result.get("payment_address"):
                report.append(f"- **Адрес:** `{result['payment_address']}`")
            
            # Обработка транзакций (может быть несколько для частичных платежей)
            if result.get("transaction_signature"):
                report.append(f"- **Транзакция:** [{result['transaction_signature']}]({result['solscan_url']})")
                report.append(f"- **Solscan:** [Просмотр транзакции]({result['solscan_url']})")
            
            # Обработка множественных транзакций для завершенных частичных платежей
            if result.get("first_transaction_signature"):
                report.append(f"- **Первая транзакция:** [{result['first_transaction_signature']}]({result['first_solscan_url']})")
            if result.get("second_transaction_signature"):
                report.append(f"- **Вторая транзакция:** [{result['second_transaction_signature']}]({result['second_solscan_url']})")
            
            if result.get("status_checks"):
                report.append("- **Проверки статуса:**")
                for check in result["status_checks"]:
                    report.append(f"  - {check['check']}: {check['status']} ({check['timestamp']})")
            
            report.append(f"- **Время выполнения:** {result['start_time']} - {result['end_time']}")
            report.append("")
        
        # Ссылки на все транзакции
        report.append("## 🔗 Ссылки на транзакции в Solscan")
        report.append("")
        
        transaction_count = 0
        for result in results:
            if result.get("transaction_signature"):
                transaction_count += 1
                report.append(f"{transaction_count}. **{result['test_name']}**")
                report.append(f"   - [{result['transaction_signature']}]({result['solscan_url']})")
            
            # Обработка множественных транзакций
            if result.get("first_transaction_signature"):
                transaction_count += 1
                report.append(f"{transaction_count}. **{result['test_name']} (Первая транзакция)**")
                report.append(f"   - [{result['first_transaction_signature']}]({result['first_solscan_url']})")
            
            if result.get("second_transaction_signature"):
                transaction_count += 1
                report.append(f"{transaction_count}. **{result['test_name']} (Вторая транзакция)**")
                report.append(f"   - [{result['second_transaction_signature']}]({result['second_solscan_url']})")
            
            if result.get("third_transaction_signature"):
                transaction_count += 1
                report.append(f"{transaction_count}. **{result['test_name']} (Третья транзакция)**")
                report.append(f"   - [{result['third_transaction_signature']}]({result['third_solscan_url']})")
        
        if transaction_count == 0:
            report.append("Нет транзакций для отображения.")
        
        report.append("")
        
        # Заключение
        report.append("## 📝 Заключение")
        if successful_tests == total_tests:
            report.append("🎉 Все тесты прошли успешно! Библиотека Solana Payments работает корректно.")
        elif successful_tests > 0:
            report.append(f"⚠️ Частичный успех: {successful_tests} из {total_tests} тестов прошли успешно.")
        else:
            report.append("❌ Все тесты завершились неудачно. Требуется отладка.")
        
        report.append("")
        report.append("---")
        report.append("*Отчет сгенерирован автоматически системой тестирования Solana Payments*")
        
        return "\n".join(report)
    
    async def run_all_tests(self) -> None:
        """Запуск всех тестов"""
        try:
            logger.info("🚀 Starting Solana Payments Devnet Tests")
            logger.info("=" * 60)
            
            # Инициализация
            logger.info("🔧 Initializing Solana Payments...")
            await initialize(self.config)
            logger.info("✅ Initialization complete")
            
            # Очистка заблокированных кошельков
            logger.info("🧹 Cleaning up locked wallets...")
            await self.cleanup_locked_wallets()
            logger.info("✅ Locked wallets cleaned up")
            
            # Настройка тестового кошелька
            logger.info("🔑 Setting up test wallet...")
            await self.setup_test_wallet()
            logger.info("✅ Test wallet ready")
            
            # Запуск тестов
            results = []
            
            # Тест отмены (не требует отправки SOL)
            logger.info("\n🧪 Running cancellation test...")
            cancellation_result = await self.test_cancellation()
            results.append(cancellation_result)
            
            # Тесты с реальными транзакциями
            logger.info("\n🧪 Running payment tests...")
            payment_results = await self.test_multiple_payments()
            results.extend(payment_results)
            
            # Тесты частичных платежей
            logger.info("\n🧪 Running partial payment tests...")
            partial_payment_results = await self.test_partial_payments()
            results.extend(partial_payment_results)
            
            # Генерация отчета
            logger.info("\n📊 Generating test report...")
            report = self.generate_report(results)
            
            # Сохранение отчета
            report_filename = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info(f"📄 Report saved: {report_filename}")
            
            # Вывод краткого отчета в консоль
            print("\n" + "=" * 60)
            print("📊 КРАТКИЙ ОТЧЕТ О ТЕСТАХ")
            print("=" * 60)
            
            total_tests = len(results)
            successful_tests = sum(1 for r in results if r.get("success", False))
            
            print(f"Всего тестов: {total_tests}")
            print(f"Успешных: {successful_tests}")
            print(f"Неудачных: {total_tests - successful_tests}")
            print(f"Успешность: {(successful_tests/total_tests*100):.1f}%")
            print("")
            
            # Ссылки на транзакции
            transactions = [r for r in results if r.get("transaction_signature")]
            if transactions:
                print("🔗 Ссылки на транзакции:")
                for i, result in enumerate(transactions, 1):
                    print(f"{i}. {result['test_name']}: {result['solscan_url']}")
            
            print(f"\n📄 Полный отчет: {report_filename}")
            
        except Exception as e:
            logger.error(f"❌ Test suite failed: {e}")
            raise
        finally:
            logger.info("\n🧹 Cleaning up...")
            
            # Очистка заблокированных кошельков
            try:
                await self.cleanup_locked_wallets()
            except Exception as e:
                logger.warning(f"Failed to cleanup wallets: {e}")
            
            await cleanup()
            logger.info("✅ Cleanup complete")


async def main():
    """Главная функция для запуска тестов"""
    tester = DevnetTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    print("🧪 Solana Payments Devnet Test Suite")
    print("=" * 60)
    print("⚠️  ВНИМАНИЕ: Этот тест создает реальные транзакции в Solana Devnet")
    print("💰 Требуется подключение к интернету и доступ к Solana RPC")
    print("=" * 60)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Тесты прерваны пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        print("\n🔧 Возможные причины:")
        print("1. Нет подключения к интернету")
        print("2. Solana RPC недоступен")
        print("3. Проблемы с MongoDB или Redis")
        print("4. Недостаточно SOL для airdrop")
