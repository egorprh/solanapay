# 🧪 Solana Payments Devnet Testing

Полное тестирование библиотеки Solana Payments в реальной среде Solana Devnet с созданием настоящих транзакций и генерацией отчетов.

## 🎯 Что тестируется

- ✅ **Создание платежей** - генерация адресов и сохранение в БД
- ✅ **Реальные транзакции** - отправка SOL в devnet
- ✅ **Обнаружение платежей** - автоматическое определение поступления средств
- ✅ **Отмена платежей** - корректная отмена и освобождение кошельков
- ✅ **Отчеты** - генерация отчетов с ссылками на Solscan

## 🚀 Быстрый запуск

### Автоматический запуск (рекомендуется)

```bash
# Один скрипт для всего
python run_devnet_tests.py
```

### Ручной запуск

```bash
# 1. Настройка devnet
python setup_devnet.py

# 2. Запуск тестов
python test_devnet.py
```

## 📋 Требования

### Инфраструктура
- **MongoDB** - для хранения платежей и кошельков
- **Redis** - для блокировки кошельков
- **Интернет** - для подключения к Solana Devnet RPC

### Python зависимости
```bash
pip install -r requirements.txt
```

### Запуск сервисов

#### Вариант A: Docker (рекомендуется)
```bash
docker-compose up -d
```

#### Вариант B: Локально
```bash
# macOS
brew services start mongodb-community
brew services start redis

# Linux
sudo systemctl start mongod
sudo systemctl start redis
```

## 🧪 Типы тестов

### 1. Тест отмены платежа
- Создает платеж
- Отменяет его
- Проверяет корректность отмены

### 2. Тест малого платежа (0.01 SOL)
- Создает платеж
- Отправляет 0.01 SOL
- Проверяет обнаружение

### 3. Тест среднего платежа (0.05 SOL)
- Создает платеж
- Отправляет 0.05 SOL
- Проверяет обнаружение

### 4. Тест большого платежа (0.1 SOL)
- Создает платеж
- Отправляет 0.1 SOL
- Проверяет обнаружение

## 📊 Отчет о тестах

После завершения тестов генерируется подробный отчет в формате Markdown:

### Структура отчета

```markdown
# 🧪 Solana Payments Devnet Test Report

## 📊 Статистика тестов
- Всего тестов: 4
- Успешных: 4
- Неудачных: 0
- Успешность: 100.0%

## 🔍 Детальные результаты

### 1. ✅ Small Payment Test
- Получено: 0.01 SOL
- Эквивалент: $2.50
- Транзакция: [signature](https://solscan.io/tx/...)
- Solscan: [Просмотр транзакции](https://solscan.io/tx/...)

## 🔗 Ссылки на транзакции в Solscan
1. [Small Payment Test](https://solscan.io/tx/...)
2. [Medium Payment Test](https://solscan.io/tx/...)
3. [Large Payment Test](https://solscan.io/tx/...)
```

### Файл отчета
- **Имя:** `test_report_YYYYMMDD_HHMMSS.md`
- **Расположение:** В корне проекта
- **Формат:** Markdown с ссылками на Solscan

## 🔗 Полезные ссылки

### Solana Devnet
- **RPC:** https://api.devnet.solana.com
- **Explorer:** https://explorer.solana.com/?cluster=devnet
- **Solscan:** https://solscan.io/?cluster=devnet
- **Faucet:** https://faucet.solana.com/

### Мониторинг транзакций
- **Solscan Devnet:** https://solscan.io/?cluster=devnet
- **Solana Explorer Devnet:** https://explorer.solana.com/?cluster=devnet

## 🛠️ Настройка и конфигурация

### Devnet конфигурация
```python
config = Config()
config.SOLANA_RPC_URL = "https://api.devnet.solana.com"
config.SOLANA_COMMITMENT = "confirmed"
```

### Тестовые кошельки
- Используются 2 предоставленных кошелька:
  - `849xjpLmgsdhQVwmkbWhP7EkzYDdo3unD3N8GY57tkon`
  - `7kFnAf3anAerYByZYEKAsPnz2eXwHFJWuZa4eV5r9wxT`
- Сохраняются в MongoDB
- Используются для получения платежей

### Airdrop SOL
- Автоматический запрос airdrop в devnet
- 2 SOL для тестового кошелька
- Проверка баланса после получения

## 🔍 Отладка и устранение неполадок

### Ошибка подключения к Devnet
```
❌ Error: Failed to get Solana balance
```

**Решения:**
1. Проверьте интернет-соединение
2. Попробуйте другой RPC endpoint
3. Проверьте доступность Solana Devnet

### Ошибка airdrop
```
❌ Error: Airdrop failed
```

**Решения:**
1. Подождите несколько минут (лимиты airdrop)
2. Используйте faucet вручную: https://faucet.solana.com/
3. Проверьте правильность адреса кошелька

### Платеж не обнаружен
```
❌ Error: Payment not detected after 5 attempts
```

**Решения:**
1. Увеличьте время ожидания между проверками
2. Проверьте правильность адреса получателя
3. Убедитесь, что транзакция подтверждена

### Ошибка MongoDB/Redis
```
❌ Error: Connection refused
```

**Решения:**
1. Запустите сервисы: `brew services start mongodb-community redis`
2. Или используйте Docker: `docker-compose up -d`
3. Проверьте порты: MongoDB (27017), Redis (6379)

## 📈 Мониторинг производительности

### Метрики тестирования
- **Время создания платежа:** ~1-2 секунды
- **Время обнаружения платежа:** ~3-10 секунд
- **Время подтверждения транзакции:** ~1-3 секунды
- **Общее время теста:** ~2-5 минут

### Логирование
```python
# Настройка уровня логирования
import logging
logging.basicConfig(level=logging.INFO)

# Логи включают:
# - Создание платежей
# - Отправку транзакций
# - Проверку статусов
# - Ошибки и предупреждения
```

## 🎯 Результаты тестирования

### Ожидаемые результаты
- ✅ Все тесты проходят успешно
- ✅ Платежи обнаруживаются автоматически
- ✅ Генерируется отчет с ссылками на Solscan
- ✅ Кошельки корректно освобождаются

### Критерии успеха
1. **100% успешность** - все тесты проходят
2. **Быстрое обнаружение** - платежи обнаруживаются за 3-10 секунд
3. **Корректные суммы** - точное определение количества SOL
4. **Валидные ссылки** - все ссылки на Solscan работают

## 🔄 Непрерывное тестирование

### Автоматизация
```bash
# Запуск тестов по расписанию
crontab -e

# Добавить строку для ежедневного тестирования
0 9 * * * cd /path/to/solana_payments && python run_devnet_tests.py
```

### CI/CD интеграция
```yaml
# GitHub Actions пример
name: Devnet Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run devnet tests
        run: python run_devnet_tests.py
```

## 📞 Поддержка

При возникновении проблем:

1. **Проверьте логи** - все ошибки логируются подробно
2. **Проверьте сервисы** - MongoDB и Redis должны быть запущены
3. **Проверьте интернет** - требуется доступ к Solana Devnet
4. **Проверьте отчет** - в отчете есть детальная информация об ошибках


{
  "created_at": "2025-09-14T21:29:22.203805",
  "network": "solana_devnet",
  "public_key": "H6aLaK4cuFzqsDSHLKXYfyXJLtEpWpKS7BYbhf1Z3zLn",
  "private_key_hex": "57625c875c97f047a1a4c5fc22e998f63313b96242af9b43756eb8729eca287a",
  "seed_phrase": "adult adult abandon admit admit action absorb abandon address above add absurd",
  "note": "Test wallet for Solana Payments testing"
}

---

**Версия:** 1.0.0  
**Автор:** Solana Payments Team  
**Дата:** 2024
