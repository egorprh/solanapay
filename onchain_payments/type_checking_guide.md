# Руководство по проверке типов для OnChain Payments Service

## Обзор

Все методы в проекте OnChain Payments Service теперь имеют подробные аннотации типов. Это руководство поможет вам настроить и использовать статическую проверку типов.

## Установка инструментов

### 1. Установка mypy
```bash
pip install mypy
```

### 2. Установка дополнительных типов
```bash
pip install types-aiohttp types-redis
```

### 3. Установка для разработки
```bash
pip install -r requirements-dev.txt
```

## Настройка mypy

### 1. Создание конфигурационного файла `mypy.ini`
```ini
[mypy]
python_version = 3.12
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
disallow_untyped_decorators = True
no_implicit_optional = True
warn_redundant_casts = True
warn_unused_ignores = True
warn_no_return = True
warn_unreachable = True
strict_equality = True

# Игнорирование отсутствующих импортов для внешних библиотек
[mypy-ormsgpack.*]
ignore_missing_imports = True

[mypy-nats.*]
ignore_missing_imports = True

[mypy-web3.*]
ignore_missing_imports = True

[mypy-motor.*]
ignore_missing_imports = True

[mypy-redis.*]
ignore_missing_imports = True

[mypy-pydantic.*]
ignore_missing_imports = True

[mypy-aiohttp.*]
ignore_missing_imports = True

# Игнорирование модулей src.core (если они не доступны)
[mypy-src.core.*]
ignore_missing_imports = True
```

### 2. Альтернативная конфигурация через `pyproject.toml`
```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true

[[tool.mypy.overrides]]
module = [
    "ormsgpack.*",
    "nats.*",
    "web3.*",
    "motor.*",
    "redis.*",
    "pydantic.*",
    "aiohttp.*",
    "src.core.*"
]
ignore_missing_imports = true
```

## Запуск проверки типов

### 1. Базовая проверка
```bash
mypy onchain_payments/
```

### 2. Строгая проверка
```bash
mypy --strict onchain_payments/
```

### 3. Проверка с подробным выводом
```bash
mypy --show-error-codes --show-column-numbers onchain_payments/
```

### 4. Проверка с кэшированием
```bash
mypy --cache-dir .mypy_cache onchain_payments/
```

## Интеграция с IDE

### VS Code
1. Установите расширение "Python" от Microsoft
2. Установите расширение "Pylance"
3. Настройте `settings.json`:
```json
{
    "python.analysis.typeCheckingMode": "strict",
    "python.analysis.autoImportCompletions": true,
    "python.analysis.diagnosticMode": "workspace"
}
```

### PyCharm
1. Включите проверку типов: Settings → Editor → Inspections → Python → Type checker
2. Выберите "mypy" как тип checker
3. Настройте путь к mypy в Settings → Tools → External Tools

## Примеры использования

### 1. Проверка конкретного файла
```bash
mypy onchain_payments/logic/payments.py
```

### 2. Проверка с игнорированием ошибок импорта
```bash
mypy --ignore-missing-imports onchain_payments/
```

### 3. Проверка с выводом в файл
```bash
mypy onchain_payments/ > type_check_results.txt
```

## Автоматизация

### 1. Pre-commit hook
Создайте файл `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [types-aiohttp, types-redis]
        args: [--ignore-missing-imports]
```

### 2. GitHub Actions
Создайте файл `.github/workflows/type-check.yml`:
```yaml
name: Type Check

on: [push, pull_request]

jobs:
  type-check:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    - name: Install dependencies
      run: |
        pip install -r requirements-detailed.txt
        pip install mypy types-aiohttp types-redis
    - name: Run mypy
      run: mypy --ignore-missing-imports onchain_payments/
```

## Решение常见问题

### 1. Ошибки импорта
Если mypy не может найти импорты, добавьте их в `mypy.ini`:
```ini
[mypy-имя_модуля.*]
ignore_missing_imports = True
```

### 2. Ошибки типов в сторонних библиотеках
Используйте `# type: ignore` для конкретных строк:
```python
import some_library  # type: ignore
```

### 3. Ошибки с Optional типами
Убедитесь, что используете `Optional[T]` вместо `T | None` для совместимости:
```python
from typing import Optional

def func() -> Optional[str]:
    return None
```

## Лучшие практики

### 1. Всегда указывайте типы возвращаемых значений
```python
def get_balance() -> float:
    return 0.0
```

### 2. Используйте Optional для nullable значений
```python
def find_payment(payment_id: str) -> Optional[Payment]:
    return None
```

### 3. Аннотируйте сложные типы
```python
def process_payments(payments: List[Dict[str, Any]]) -> Dict[str, float]:
    return {}
```

### 4. Используйте Union для множественных типов
```python
from typing import Union

def process_data(data: Union[str, int, float]) -> str:
    return str(data)
```

### 5. Аннотируйте асинхронные функции
```python
async def async_function() -> None:
    pass
```

## Мониторинг качества типов

### 1. Отчет о покрытии типов
```bash
mypy --html-report mypy-report onchain_payments/
```

### 2. Статистика типов
```bash
mypy --show-traceback onchain_payments/
```

### 3. Проверка в CI/CD
Добавьте проверку типов в ваш pipeline для автоматической проверки при каждом коммите.

## Заключение

Добавление аннотаций типов значительно улучшает качество кода, делает его более читаемым и помогает предотвратить ошибки на этапе разработки. Регулярное использование mypy поможет поддерживать высокое качество кода в проекте.
