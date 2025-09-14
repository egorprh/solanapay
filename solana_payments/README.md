# Solana Payments Library

Библиотека для обработки платежей в сети Solana. Предоставляет простые функции для создания, отслеживания и отмены платежей в SOL, USDC и USDT, включая поддержку частичных платежей.

## Структура проекта

```
solana_payments/
├── solana_payments.py              # Основная библиотека
├── partial_payment.py # Модуль для очистки истекших платежей
├── __init__.py                     # Экспорты библиотеки
├── requirements.txt                # Зависимости
├── docker-compose.yml              # Docker для MongoDB и Redis
├── README.md                       # Документация
└── tests/                          # Тесты и утилиты
    ├── __init__.py
    ├── test_example.py             # Базовые тесты
    ├── test_devnet.py              # Devnet тесты с реальными транзакциями
    ├── test_partial_payment_cleanup.py # Тесты очистки частичных платежей
    ├── setup_database.py           # Настройка базы данных
    ├── setup_devnet.py             # Настройка devnet
    ├── run_devnet_tests.py         # Автоматизированные тесты
    └── TESTING_GUIDE.md            # Полное руководство по тестированию
```

## Особенности

- 🚀 **Простота использования** - один файл, прямые вызовы функций
- ⚡ **Высокая производительность** - асинхронная работа с Solana RPC
- 🔒 **Безопасность** - управление пулом кошельков с блокировками
- 📊 **Мониторинг** - автоматическое отслеживание поступления средств
- 💰 **Поддержка токенов** - SOL, USDC, USDT
- 🗄️ **Персистентность** - интеграция с MongoDB и Redis
- 🧪 **Полное тестирование** - тесты с реальными транзакциями в Devnet
- 💳 **Частичные платежи** - поддержка оплаты частями с автоматической очисткой

## Установка

### Основные зависимости

```bash
pip install -r requirements.txt
```

### Для разработки

```bash
pip install -r requirements-dev.txt
```

### Точные версии (для воспроизводимых сборок)

```bash
pip install -r requirements-exact.txt
```

### Системные требования

- Python 3.8+
- MongoDB 4.4+
- Redis 6.0+
- Подключение к интернету для Solana RPC

## Быстрый старт

### Базовое использование

```python
import asyncio
import uuid
from solana_payments import initialize, create_payment, get_payment_status, cleanup

async def main():
    # Инициализация библиотеки
    await initialize()
    
    # Создание платежа
    payment_id = str(uuid.uuid4())
    payment = await create_payment(payment_id, "sol")
    print(f"Payment address: {payment['payment_address']}")
    
    # Проверка статуса
    status = await get_payment_status(payment_id)
    print(f"Status: {status['status']}")
    
    # Очистка ресурсов
    await cleanup()

# Запуск
asyncio.run(main())
```

### Частичные платежи

```python
import asyncio
import uuid
from solana_payments import initialize, create_payment, get_payment_status, get_payment_summary, cleanup

async def main():
    await initialize()
    
    # Создаем заказ на 100 SOL с возможностью частичной оплаты
    payment_id = str(uuid.uuid4())
    payment = await create_payment(payment_id, "sol", expected_amount=100.0)
    
    print(f"Отправьте {payment['expected_amount']} SOL на: {payment['payment_address']}")
    
    # Пользователь отправляет 30 SOL
    status = await get_payment_status(payment_id)
    print(f"Статус: {status['status']}")  # "partial"
    print(f"Оплачено: {status['paid_amount']} SOL")
    print(f"Осталось: {status['remaining_amount']} SOL")
    
    # Получение детальной информации
    summary = await get_payment_summary(payment_id)
    print(f"Можно доплачивать: {summary['can_continue_payment']}")
    print(f"Количество частичных платежей: {summary['partial_payments_count']}")
    
    # Пользователь отправляет еще 70 SOL
    status = await get_payment_status(payment_id)
    print(f"Статус: {status['status']}")  # "paid"
    print(f"Полностью оплачено: {status['paid_amount']} SOL")
    
    await cleanup()

asyncio.run(main())
```

## Тестирование

### Базовые тесты

```bash
cd tests
python3 test_example.py
```

### Devnet тесты с реальными транзакциями (включая частичные платежи)

```bash
cd tests
python3 run_devnet_tests.py
```

### Тесты очистки частичных платежей

```bash
cd tests
python3 test_partial_payment_cleanup.py
```

### Настройка базы данных

```bash
cd tests
python3 setup_database.py
```

### Настройка devnet

```bash
cd tests
python3 setup_devnet.py
```

## API Reference

### Инициализация

#### `initialize(config=None)`

Инициализирует подключения к Solana RPC, MongoDB и Redis.

**Параметры:**
- `config` (Config, optional): Конфигурация библиотеки

**Пример:**
```python
from solana_payments import initialize, Config

# С кастомной конфигурацией
config = Config()
config.SOLANA_RPC_URL = "https://api.devnet.solana.com"
config.MONGODB_URL = "mongodb://localhost:27017"

await initialize(config)
```

### Основные функции

#### `create_payment(payment_id, token, expected_amount=None)`

Создает новый платеж и возвращает адрес для получения средств.

**Параметры:**
- `payment_id` (str): Уникальный идентификатор платежа
- `token` (str): Тип токена ("sol", "usdc", "usdt")
- `expected_amount` (float, optional): Ожидаемая сумма для частичных платежей

**Возвращает:**
```python
{
    "payment_id": "uuid-string",
    "token": "sol",
    "payment_address": "Solana-address",
    "status": "pending",
    "initial_balance": 0.0,
    "expected_amount": 100.0,  # Если указана
    "paid_amount": 0.0,
    "remaining_amount": 100.0,  # Если указана expected_amount
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
}
```

**Примеры:**
```python
# Обычный платеж
payment = await create_payment("payment-123", "sol")

# Платеж с ожидаемой суммой (частичные платежи)
payment = await create_payment("order-456", "sol", expected_amount=100.0)
```

#### `get_payment_status(payment_id)`

Проверяет статус платежа и обновляет его при поступлении средств.

**Параметры:**
- `payment_id` (str): Идентификатор платежа

**Возвращает:**
```python
{
    "payment_id": "uuid-string",
    "token": "sol",
    "payment_address": "Solana-address",
    "status": "paid",  # "pending", "partial", "paid", "overpaid", "cancelled"
    "payment_amount": 0.1,
    "outcome_amount": 20.0,
    "expected_amount": 100.0,  # Если указана
    "paid_amount": 100.0,      # Сумма всех частичных платежей
    "remaining_amount": 0.0,   # Остаток к доплате
    "partial_payments": [      # История частичных платежей
        {
            "amount": 30.0,
            "timestamp": "2024-01-01T12:00:00",
            "balance_after": 30.0
        },
        {
            "amount": 70.0,
            "timestamp": "2024-01-01T12:05:00",
            "balance_after": 100.0
        }
    ],
    "transaction_signature": "tx-signature",
    "updated_at": "2024-01-01T00:00:00"
}
```

**Пример:**
```python
status = await get_payment_status("payment-123")
if status["status"] == "paid":
    print(f"Received {status['payment_amount']} SOL")
elif status["status"] == "partial":
    print(f"Partial payment: {status['paid_amount']} SOL, remaining: {status['remaining_amount']} SOL")
```

#### `get_payment_summary(payment_id)` (новая функция)

Возвращает детальную информацию о платеже.

**Параметры:**
- `payment_id` (str): Идентификатор платежа

**Возвращает:**
```python
{
    "payment_id": "uuid-string",
    "status": "partial",
    "expected_amount": 100.0,
    "paid_amount": 30.0,
    "remaining_amount": 70.0,
    "partial_payments_count": 1,
    "can_continue_payment": True,
    "is_fully_paid": False,
    "is_overpaid": False
}
```

**Пример:**
```python
summary = await get_payment_summary("payment-123")
print(f"Can continue payment: {summary['can_continue_payment']}")
print(f"Is fully paid: {summary['is_fully_paid']}")
```

#### `cancel_payment(payment_id)`

Отменяет платеж и освобождает кошелек.

**Параметры:**
- `payment_id` (str): Идентификатор платежа

**Возвращает:**
```python
{
    "payment_id": "uuid-string",
    "status": "cancelled",
    "updated_at": "2024-01-01T00:00:00"
}
```

**Пример:**
```python
cancelled = await cancel_payment("payment-123")
print(f"Payment cancelled: {cancelled['status']}")
```

#### `check_payment_received(payment_id)`

Быстрая проверка поступления платежа без обновления БД.

**Параметры:**
- `payment_id` (str): Идентификатор платежа

**Возвращает:**
- `bool`: True если платеж поступил, False в противном случае

**Пример:**
```python
received = await check_payment_received("payment-123")
if received:
    print("Payment received!")
```

#### `cleanup()`

Закрывает все подключения к внешним сервисам.

**Пример:**
```python
await cleanup()
```

## Частичные платежи

### Обзор

Библиотека поддерживает частичные платежи, что позволяет пользователям оплачивать заказы частями. Это особенно полезно для крупных сумм или когда пользователь хочет разделить платеж на несколько транзакций.

### Статусы платежей

- `pending` - ожидает полной оплаты
- `partial` - получена частичная оплата, можно доплачивать
- `paid` - получена полная сумма
- `overpaid` - получена сумма больше ожидаемой
- `cancelled` - отменен

### Примеры использования

#### Пример 1: Частичная оплата заказа

```python
import asyncio
import uuid
from solana_payments import initialize, create_payment, get_payment_status, cleanup

async def main():
    await initialize()
    
    # Создаем заказ на 100 SOL
    payment_id = str(uuid.uuid4())
    payment = await create_payment(payment_id, "sol", expected_amount=100.0)
    
    print(f"Отправьте {payment['expected_amount']} SOL на: {payment['payment_address']}")
    
    # Пользователь отправляет 30 SOL
    status = await get_payment_status(payment_id)
    print(f"Статус: {status['status']}")  # "partial"
    print(f"Оплачено: {status['paid_amount']} SOL")
    print(f"Осталось: {status['remaining_amount']} SOL")
    
    # Пользователь отправляет еще 70 SOL
    status = await get_payment_status(payment_id)
    print(f"Статус: {status['status']}")  # "paid"
    print(f"Полностью оплачено: {status['paid_amount']} SOL")
    
    await cleanup()

asyncio.run(main())
```

#### Пример 2: Обработка переплаты

```python
# Пользователь отправляет 120 SOL вместо 100 SOL
status = await get_payment_status(payment_id)
print(f"Статус: {status['status']}")  # "overpaid"
print(f"Оплачено: {status['paid_amount']} SOL")  # 120.0
print(f"Переплата: {status['paid_amount'] - status['expected_amount']} SOL")  # 20.0
```

#### Пример 3: Отмена частично оплаченного платежа

```python
# Пользователь оплатил 50 SOL из 100 SOL, но передумал
status = await get_payment_status(payment_id)
print(f"Статус: {status['status']}")  # "partial"

# Отменяем платеж
cancelled = await cancel_payment(payment_id)
print(f"Статус после отмены: {cancelled['status']}")  # "cancelled"
```

## Автоматическая очистка истекших платежей

### Проблема

При частичной оплате кошелек остается заблокированным на 1 час (TTL в Redis), но статус платежа не обновляется автоматически. Это приводит к:

1. **Неэффективному использованию пула кошельков** - кошельки остаются заблокированными даже после истечения времени
2. **Некорректным статусам платежей** - платежи остаются со статусом `partial` даже после освобождения кошелька
3. **Потенциальным конфликтам** - один кошелек может быть "заблокирован" в Redis и "свободен" в базе данных

### Решение

Добавлен модуль `partial_payment.py` с функциями для автоматической очистки истекших частичных платежей.

### Использование модуля очистки

#### Ручная очистка

```python
import asyncio
from solana_payments import SolanaPayments, Config
from partial_payment import PartialPaymentManager

async def manual_cleanup():
    # Инициализация
    payments = SolanaPayments()
    await payments.initialize(Config())
    
    # Создание менеджера
    manager = PartialPaymentManager(payments)
    
    # Получение статистики
    status = await manager.get_partial_payments_status()
    print(f"Заблокированных кошельков: {status['locked_wallets_count']}")
    
    # Очистка истекших платежей
    result = await manager.cleanup_expired_payments()
    print(f"Очищено платежей: {result['total_cancelled']}")
    
    await payments.cleanup()

asyncio.run(manual_cleanup())
```

#### Автоматическая очистка

```python
import asyncio
from solana_payments import SolanaPayments, Config
from partial_payment import start_cleanup_scheduler

async def auto_cleanup():
    # Инициализация
    payments = SolanaPayments()
    await payments.initialize(Config())
    
    # Запуск планировщика очистки каждые 30 минут
    cleanup_task = asyncio.create_task(
        start_cleanup_scheduler(payments, interval_minutes=30)
    )
    
    try:
        # Основная логика приложения
        while True:
            # Ваша бизнес-логика
            await asyncio.sleep(60)
    finally:
        cleanup_task.cancel()
        await payments.cleanup()

asyncio.run(auto_cleanup())
```

#### Интеграция в веб-приложение

```python
from fastapi import FastAPI, BackgroundTasks
from solana_payments import SolanaPayments, Config
from partial_payment import PartialPaymentManager, start_cleanup_scheduler

app = FastAPI()
payments = SolanaPayments()
manager = PartialPaymentManager(payments)

@app.on_event("startup")
async def startup():
    await payments.initialize(Config())
    # Запуск планировщика очистки
    asyncio.create_task(
        start_cleanup_scheduler(payments, interval_minutes=30)
    )

@app.get("/admin/cleanup")
async def manual_cleanup():
    result = await manager.cleanup_expired_payments()
    return {"message": f"Cleaned up {result['total_cancelled']} payments"}

@app.get("/admin/status")
async def get_status():
    return await manager.get_partial_payments_status()
```

## Конфигурация

### Config класс

```python
class Config:
    # Solana настройки
    SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
    SOLANA_COMMITMENT = "confirmed"
    SOLANA_TIMEOUT = 30
    
    # MongoDB настройки
    MONGODB_URL = "mongodb://localhost:27017"
    MONGODB_DATABASE = "solana_payments"
    
    # Redis настройки
    REDIS_URL = "redis://localhost:6379"
    REDIS_DB = 0
    
    # CoinGecko API
    COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
    COINGECKO_TIMEOUT = 10
    
    # Настройки кошельков
    WALLET_POOL_SIZE = 100
    WALLET_LOCK_TIMEOUT = 3600  # 1 час
```

## Поддерживаемые токены

| Токен | Описание | Адрес контракта |
|-------|----------|-----------------|
| SOL | Нативная валюта Solana | - |
| USDC | USD Coin | EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v |
| USDT | Tether | Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB |

## Требования к инфраструктуре

### MongoDB

Создайте коллекции для хранения данных:

```javascript
// Коллекция платежей
db.payments.createIndex({ "payment_id": 1 }, { unique: true })
db.payments.createIndex({ "status": 1 })
db.payments.createIndex({ "created_at": 1 })

// Коллекция кошельков
db.wallets.insertOne({
    "network": "solana",
    "addresses": [
        "wallet-address-1",
        "wallet-address-2",
        // ... больше адресов
    ]
})
```

### Redis

Используется для блокировки кошельков:
- Ключи: `occupied_wallet:solana:{address}`
- TTL: 1 час (3600 секунд)

## Примеры использования

### Telegram Bot

```python
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from solana_payments import initialize, create_payment, get_payment_status

async def start_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание платежа через Telegram бота"""
    payment_id = str(uuid.uuid4())
    payment = await create_payment(payment_id, "sol")
    
    message = f"""
💳 Создан платеж #{payment_id[:8]}

💰 Сумма: SOL
📍 Адрес: `{payment['payment_address']}`

Отправьте SOL на указанный адрес для завершения платежа.
    """
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def check_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка статуса платежа"""
    payment_id = context.args[0] if context.args else None
    
    if not payment_id:
        await update.message.reply_text("Укажите ID платежа")
        return
    
    status = await get_payment_status(payment_id)
    
    if status["status"] == "paid":
        message = f"✅ Платеж получен!\n💰 Сумма: {status['payment_amount']} SOL"
    elif status["status"] == "partial":
        message = f"⏳ Частичная оплата: {status['paid_amount']} SOL\n📊 Осталось: {status['remaining_amount']} SOL"
    else:
        message = f"⏳ Платеж в обработке...\n📍 Адрес: {status['payment_address']}"
    
    await update.message.reply_text(message)

# Инициализация бота
async def main():
    await initialize()
    
    app = Application.builder().token("YOUR_BOT_TOKEN").build()
    app.add_handler(CommandHandler("pay", start_payment))
    app.add_handler(CommandHandler("check", check_payment))
    
    await app.run_polling()

asyncio.run(main())
```

### Web Application

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
from solana_payments import initialize, create_payment, get_payment_status

app = FastAPI()

class PaymentRequest(BaseModel):
    token: str
    expected_amount: float = None

class PaymentResponse(BaseModel):
    payment_id: str
    payment_address: str
    status: str
    expected_amount: float = None

@app.on_event("startup")
async def startup():
    await initialize()

@app.post("/payments", response_model=PaymentResponse)
async def create_payment_endpoint(request: PaymentRequest):
    try:
        payment_id = str(uuid.uuid4())
        payment = await create_payment(payment_id, request.token, request.expected_amount)
        return PaymentResponse(**payment)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/payments/{payment_id}")
async def get_payment_endpoint(payment_id: str):
    try:
        status = await get_payment_status(payment_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/payments/{payment_id}/summary")
async def get_payment_summary_endpoint(payment_id: str):
    try:
        from solana_payments import get_payment_summary
        summary = await get_payment_summary(payment_id)
        return summary
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
```

## Обработка ошибок

Библиотека использует стандартные Python исключения:

```python
try:
    payment = await create_payment("payment-123", "sol")
except Exception as e:
    print(f"Ошибка создания платежа: {e}")
```

### Типичные ошибки:

- `"SolanaPayments not initialized"` - не вызвана функция `initialize()`
- `"No available wallets in pool"` - нет свободных кошельков
- `"Payment not found"` - платеж не найден в БД
- `"Invalid Solana address format"` - некорректный адрес

## Логирование

Библиотека использует стандартный Python logging:

```python
import logging

# Настройка уровня логирования
logging.basicConfig(level=logging.INFO)

# В коде будут видны логи:
# INFO - успешные операции
# WARNING - предупреждения
# ERROR - ошибки
```

## Безопасность

### Рекомендации:

1. **Приватные ключи**: Храните приватные ключи кошельков в безопасном месте
2. **RPC endpoints**: Используйте приватные Solana RPC ноды для продакшена
3. **Мониторинг**: Отслеживайте подозрительную активность
4. **Rate limiting**: Ограничивайте частоту запросов к API

### Настройка кошельков:

```python
# Создание пула кошельков
import json
from solana.keypair import Keypair

wallets = []
for i in range(100):
    keypair = Keypair()
    wallets.append(str(keypair.public_key))

# Сохранение в MongoDB
db.wallets.insert_one({
    "network": "solana",
    "addresses": wallets
})
```

## Производительность

### Оптимизация:

- Используйте connection pooling для MongoDB и Redis
- Настройте правильные индексы в MongoDB
- Используйте commit level "confirmed" для быстрых проверок
- Кэшируйте цены токенов

### Мониторинг:

- Количество активных платежей
- Доступность кошельков
- Время отклика Solana RPC
- Ошибки обработки платежей

## Обратная совместимость

Все существующие функции работают без изменений:

```python
# Старый способ (все еще работает)
payment = await create_payment("order-123", "sol")
status = await get_payment_status("order-123")

# Новый способ
payment = await create_payment("order-123", "sol", expected_amount=100.0)
summary = await get_payment_summary("order-123")
```

## Рекомендации по частичным платежам

### 1. Частота очистки

- **Активные системы**: каждые 15-30 минут
- **Средние системы**: каждый час
- **Малые системы**: каждые 2-4 часа

### 2. Мониторинг

- Регулярно проверяйте статистику через `get_partial_payments_status()`
- Настройте алерты при большом количестве истекших платежей
- Мониторьте количество заблокированных кошельков

### 3. Уведомления пользователей

- Отправляйте напоминания о недоплате за 30 минут до истечения
- Уведомляйте об отмене платежа при истечении времени

## Лицензия

MIT License

## Поддержка

Для вопросов и предложений создавайте issues в репозитории проекта.

---

**Версия:** 2.0.0  
**Автор:** Solana Payments Team  
**Дата:** 2024