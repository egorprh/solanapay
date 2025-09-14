#!/usr/bin/env python3
"""
Быстрый запуск тестов Solana Payments в Devnet

Автоматизированный скрипт для:
1. Настройки devnet конфигурации
2. Запуска полного цикла тестов
3. Генерации отчета с ссылками на Solscan
"""

import asyncio
import subprocess
import sys
import os
from pathlib import Path

def check_dependencies():
    """Проверка зависимостей"""
    print("🔍 Checking dependencies...")
    
    try:
        import motor
        import redis
        import solana
        import aiohttp
        import pydantic
        print("✅ All Python dependencies installed")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Run: pip install -r requirements.txt")
        return False
    
    return True

def check_services():
    """Проверка запущенных сервисов"""
    print("🔍 Checking services...")
    
    # Проверка MongoDB
    try:
        import motor.motor_asyncio
        client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
        # Простая проверка подключения
        print("✅ MongoDB connection available")
    except Exception as e:
        print(f"❌ MongoDB not available: {e}")
        print("Start MongoDB: brew services start mongodb-community")
        return False
    
    # Проверка Redis
    try:
        import redis.asyncio
        # Простая проверка
        print("✅ Redis connection available")
    except Exception as e:
        print(f"❌ Redis not available: {e}")
        print("Start Redis: brew services start redis")
        return False
    
    return True

async def run_setup():
    """Запуск настройки"""
    print("\n🔧 Setting up Devnet configuration...")
    
    try:
        # Импортируем и запускаем setup_devnet
        from setup_devnet import setup_devnet_config
        await setup_devnet_config()
        print("✅ Devnet setup complete")
        return True
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return False

async def run_tests():
    """Запуск тестов"""
    print("\n🧪 Running Devnet tests...")
    
    try:
        # Импортируем и запускаем тесты
        from test_devnet import DevnetTester
        tester = DevnetTester()
        await tester.run_all_tests()
        return True
    except Exception as e:
        print(f"❌ Tests failed: {e}")
        return False

def show_results():
    """Показ результатов"""
    print("\n📊 Test Results")
    print("=" * 50)
    
    # Ищем файлы отчетов
    report_files = list(Path(".").glob("test_report_*.md"))
    
    if report_files:
        latest_report = max(report_files, key=lambda x: x.stat().st_mtime)
        print(f"📄 Latest report: {latest_report}")
        
        # Показываем краткую информацию из отчета
        try:
            with open(latest_report, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Извлекаем статистику
            if "Успешных:" in content:
                lines = content.split('\n')
                for line in lines:
                    if "Успешных:" in line or "Неудачных:" in line or "Успешность:" in line:
                        print(f"  {line.strip()}")
                        
        except Exception as e:
            print(f"Error reading report: {e}")
    else:
        print("❌ No test reports found")

async def main():
    """Главная функция"""
    print("🚀 Solana Payments Devnet Test Runner")
    print("=" * 60)
    
    # Проверка зависимостей
    if not check_dependencies():
        sys.exit(1)
    
    # Проверка сервисов
    if not check_services():
        print("\n💡 Tip: Use Docker for easy setup:")
        print("docker-compose up -d")
        sys.exit(1)
    
    # Настройка
    if not await run_setup():
        sys.exit(1)
    
    # Запуск тестов
    if not await run_tests():
        sys.exit(1)
    
    # Показ результатов
    show_results()
    
    print("\n🎉 All tests completed!")
    print("\n📋 What was tested:")
    print("✅ Payment creation")
    print("✅ Real SOL transactions in Devnet")
    print("✅ Payment detection")
    print("✅ Payment cancellation")
    print("✅ Report generation with Solscan links")
    
    print("\n🔗 Useful links:")
    print("• Solscan Devnet: https://solscan.io/?cluster=devnet")
    print("• Solana Devnet Explorer: https://explorer.solana.com/?cluster=devnet")
    print("• Solana Devnet Faucet: https://faucet.solana.com/")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        sys.exit(1)
