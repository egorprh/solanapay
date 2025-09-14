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

from solana_payments import initialize, create_payment, get_payment_status, cancel_payment, cleanup, Config
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
            balance_sol = balance_response.value / 10**9
            logger.info(f"💰 Wallet balance: {balance_sol} SOL")
            
            if balance_sol < 0.1:
                logger.warning("⚠️ Low balance! Make sure the wallet has enough SOL for testing.")
                raise Exception(f"Insufficient balance: {balance_sol} SOL")
            
            await solana_client.close()
            
        except Exception as e:
            logger.error(f"❌ Failed to setup test wallet: {e}")
            raise
    
    
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
            
            logger.info(f"📤 Sending {amount_sol} SOL to {recipient_address}")
            
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
            else:
                report.append("**Статус:** Неудачно")
                if result.get("error"):
                    report.append(f"- **Ошибка:** {result['error']}")
            
            if result.get("payment_id"):
                report.append(f"- **Payment ID:** `{result['payment_id']}`")
            
            if result.get("payment_address"):
                report.append(f"- **Адрес:** `{result['payment_address']}`")
            
            if result.get("transaction_signature"):
                report.append(f"- **Транзакция:** [{result['transaction_signature']}]({result['solscan_url']})")
                report.append(f"- **Solscan:** [Просмотр транзакции]({result['solscan_url']})")
            
            if result.get("status_checks"):
                report.append("- **Проверки статуса:**")
                for check in result["status_checks"]:
                    report.append(f"  - {check['check']}: {check['status']} ({check['timestamp']})")
            
            report.append(f"- **Время выполнения:** {result['start_time']} - {result['end_time']}")
            report.append("")
        
        # Ссылки на все транзакции
        report.append("## 🔗 Ссылки на транзакции в Solscan")
        report.append("")
        
        transactions = [r for r in results if r.get("transaction_signature")]
        if transactions:
            for i, result in enumerate(transactions, 1):
                report.append(f"{i}. [{result['test_name']}]({result['solscan_url']})")
        else:
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
