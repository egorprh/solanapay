# Solana Payments Library

Библиотека для обработки платежей в сети Solana. Предоставляет простые функции для создания, отслеживания и отмены платежей в SOL, USDC и USDT.

## Структура проекта

```
solana_payments/
├── solana_payments.py      # Основная библиотека
├── __init__.py             # Экспорты библиотеки
├── requirements.txt        # Зависимости
├── docker-compose.yml      # Docker для MongoDB и Redis
├── README.md              # Документация
├── QUICKSTART.md          # Быстрый старт
└── tests/                 # Тесты и утилиты
    ├── __init__.py
    ├── test_example.py    # Базовые тесты
    ├── test_devnet.py     # Devnet тесты с реальными транзакциями
    ├── setup_database.py  # Настройка базы данных
    ├── setup_devnet.py    # Настройка devnet
    ├── run_devnet_tests.py # Автоматизированные тесты
    └── DEVNET_TESTING.md  # Документация по тестированию
```

## Особенности

- 🚀 **Простота использования** - один файл, прямые вызовы функций
- ⚡ **Высокая производительность** - асинхронная работа с Solana RPC
- 🔒 **Безопасность** - управление пулом кошельков с блокировками
- 📊 **Мониторинг** - автоматическое отслеживание поступления средств
- 💰 **Поддержка токенов** - SOL, USDC, USDT
- 🗄️ **Персистентность** - интеграция с MongoDB и Redis
- 🧪 **Полное тестирование** - тесты с реальными транзакциями в Devnet

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

## Тестирование

### Базовые тесты

```bash
cd tests
python3 test_example.py
```

### Devnet тесты с реальными транзакциями

```bash
cd tests
python3 run_devnet_tests.py
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

#### `create_payment(payment_id, token)`

Создает новый платеж и возвращает адрес для получения средств.

**Параметры:**
- `payment_id` (str): Уникальный идентификатор платежа
- `token` (str): Тип токена ("sol", "usdc", "usdt")

**Возвращает:**
```python
{
    "payment_id": "uuid-string",
    "token": "sol",
    "payment_address": "Solana-address",
    "status": "pending",
    "initial_balance": 0.0,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
}
```

**Пример:**
```python
payment = await create_payment("payment-123", "sol")
print(f"Send SOL to: {payment['payment_address']}")
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
    "status": "paid",  # "pending", "paid", "cancelled"
    "payment_amount": 0.1,
    "outcome_amount": 20.0,
    "transaction_signature": "tx-signature",
    "updated_at": "2024-01-01T00:00:00"
}
```

**Пример:**
```python
status = await get_payment_status("payment-123")
if status["status"] == "paid":
    print(f"Received {status['payment_amount']} SOL")
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
    WALLET_LOCK_TIMEOUT = 3600
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

class PaymentResponse(BaseModel):
    payment_id: str
    payment_address: str
    status: str

@app.on_event("startup")
async def startup():
    await initialize()

@app.post("/payments", response_model=PaymentResponse)
async def create_payment_endpoint(request: PaymentRequest):
    try:
        payment_id = str(uuid.uuid4())
        payment = await create_payment(payment_id, request.token)
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

## Лицензия

MIT License

## Поддержка

Для вопросов и предложений создавайте issues в репозитории проекта.

---

**Версия:** 1.0.0  
**Автор:** Solana Payments Team  
**Дата:** 2024
