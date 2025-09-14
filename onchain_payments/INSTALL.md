# Установка и настройка OnChain Payments Service

## Требования

- Python 3.8+ (рекомендуется Python 3.12.3)
- pip (менеджер пакетов Python)
- MongoDB (для хранения данных о платежах)
- Redis (для управления состоянием кошельков)
- NATS Server (для обмена сообщениями)

## Быстрая установка

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd onchain_payments
```

### 2. Создание виртуального окружения
```bash
# Создание виртуального окружения
python -m venv venv

# Активация виртуального окружения
# На Windows:
venv\Scripts\activate
# На macOS/Linux:
source venv/bin/activate
```

### 3. Установка зависимостей

#### Для продакшена:
```bash
pip install -r requirements-detailed.txt
```

#### Для разработки:
```bash
pip install -r requirements-detailed.txt
pip install -r requirements-dev.txt
```

### 4. Настройка окружения

Создайте файл `.env` в корне проекта:
```bash
# MongoDB
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_USERNAME=your_username
MONGO_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DATABASE=0

# NATS
NATS_HOST=localhost
NATS_PORT=4222

# Blockchain RPC endpoints
POLYGON_NODE_URL=https://polygon-rpc.com
ARBITRUM_NODE_URL=https://arb1.arbitrum.io/rpc
OPTIMISM_NODE_URL=https://mainnet.optimism.io
SOLANA_NODE_URL=https://api.mainnet-beta.solana.com

# CoinGecko API (опционально)
COINGECKO_API_KEY=your_api_key
```

### 5. Запуск сервиса

```bash
# Запуск основного сервиса
python -m onchain_payments

# Или через Poetry (если используется)
poetry run python -m onchain_payments
```

## Docker установка

### 1. Сборка образа
```bash
docker build -t onchain-payments .
```

### 2. Запуск контейнера
```bash
docker run -d \
  --name onchain-payments \
  --env-file .env \
  onchain-payments
```

### 3. Docker Compose (рекомендуется)
```yaml
version: '3.8'
services:
  onchain-payments:
    build: .
    environment:
      - MONGO_HOST=mongodb
      - REDIS_HOST=redis
      - NATS_HOST=nats
    depends_on:
      - mongodb
      - redis
      - nats
  
  mongodb:
    image: mongo:7.0
    ports:
      - "27017:27017"
  
  redis:
    image: redis:7.2
    ports:
      - "6379:6379"
  
  nats:
    image: nats:2.10
    ports:
      - "4222:4222"
```

## Проверка установки

### 1. Проверка зависимостей
```bash
pip list
```

### 2. Проверка импортов
```bash
python -c "import web3, nats, motor, redis, pydantic, aiohttp, ormsgpack; print('All dependencies installed successfully')"
```

### 3. Запуск тестов
```bash
pytest tests/
```

## Устранение неполадок

### Проблема: Ошибка импорта модулей
**Решение:** Убедитесь, что виртуальное окружение активировано и все зависимости установлены.

### Проблема: Ошибка подключения к MongoDB
**Решение:** Проверьте настройки подключения в `.env` файле и убедитесь, что MongoDB запущен.

### Проблема: Ошибка подключения к Redis
**Решение:** Проверьте настройки Redis и убедитесь, что сервер запущен.

### Проблема: Ошибка подключения к NATS
**Решение:** Убедитесь, что NATS Server запущен и доступен по указанному адресу.

## Обновление зависимостей

### 1. Проверка устаревших пакетов
```bash
pip list --outdated
```

### 2. Обновление всех пакетов
```bash
pip install --upgrade -r requirements-detailed.txt
```

### 3. Обновление requirements.txt
```bash
pip freeze > requirements-detailed.txt
```

## Безопасность

### 1. Сканирование уязвимостей
```bash
safety check
```

### 2. Проверка безопасности кода
```bash
bandit -r .
```

### 3. Обновление зависимостей
Регулярно обновляйте зависимости для получения исправлений безопасности.

## Мониторинг

### 1. Логирование
Сервис использует стандартное логирование Python. Настройте уровень логирования в коде.

### 2. Метрики
Рассмотрите интеграцию с системами мониторинга (Prometheus, Grafana).

### 3. Алерты
Настройте алерты для критических ошибок и недоступности сервисов.

## Поддержка

При возникновении проблем:
1. Проверьте логи сервиса
2. Убедитесь в корректности конфигурации
3. Проверьте доступность внешних сервисов
4. Обратитесь к документации используемых библиотек
