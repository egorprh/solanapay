import logging
from fastapi import FastAPI, BackgroundTasks, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from pydantic import BaseModel
from solana.rpc.api import Client
from solders.signature import Signature
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer
import os
import asyncio
from datetime import datetime, timezone
import sqlite3
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import List
import json
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis
from fastapi_limiter.middleware import RateLimitMiddleware

# Загрузка переменных окружения из .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Логирование в консоль
        logging.FileHandler("app.log", encoding="utf-8"),  # Логирование в файл
    ],
)
logger = logging.getLogger(__name__)

# Инициализация FastAPI
app = FastAPI()

# Middleware для перенаправления HTTP на HTTPS
app.add_middleware(HTTPSRedirectMiddleware)

# Middleware для CORS (можно ограничить домены)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-secure-domain.com"],  # Ограничиваем доверенные домены
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# Middleware для добавления заголовков безопасности
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.update({
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data:; "
                "connect-src 'self' https://api.devnet.solana.com; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            ),
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
        })
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Клиент Solana
solana_client = Client("https://api.devnet.solana.com")

# Генератор CSRF-токенов
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
csrf_serializer = URLSafeTimedSerializer(SECRET_KEY)

# Подключение к базе данных SQLite
DB_PATH = "transactions.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Создание таблицы для хранения транзакций
cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signature TEXT UNIQUE NOT NULL,
    seller_wallet TEXT NOT NULL,
    amount INTEGER NOT NULL,
    currency TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()


# Модель для запроса
class PaymentRequest(BaseModel):
    seller_wallet: str
    tx_signature: str
    csrf_token: str  # CSRF-токен для защиты запросов
    currency: str  # Валюта (SOL, USDC, USDT)


# Список поддерживаемых валют
SUPPORTED_CURRENCIES = ["SOL", "USDC", "USDT"]

def get_seller_wallet() -> str:
    """Получает адрес кошелька продавца из .env"""
    seller_wallet = os.getenv("SELLER_WALLET")
    if not seller_wallet:
        logger.error("Адрес кошелька продавца не найден в .env")
        raise ValueError("Адрес кошелька продавца не найден в .env")
    return seller_wallet


def save_transaction(signature: str, seller_wallet: str, amount: int, currency: str):
    """Сохраняет информацию о транзакции в базе данных"""
    try:
        cursor.execute(
            "INSERT INTO transactions (signature, seller_wallet, amount, currency) VALUES (?, ?, ?, ?)",
            (signature, seller_wallet, amount, currency),
        )
        conn.commit()
        logger.info(f"Транзакция {signature} успешно сохранена в базе данных")
    except sqlite3.IntegrityError:
        logger.warning(f"Транзакция {signature} уже существует в базе данных")
        raise HTTPException(status_code=400, detail="Транзакция уже была обработана")


def is_transaction_processed(signature: str) -> bool:
    """Проверяет, была ли транзакция уже обработана"""
    cursor.execute("SELECT 1 FROM transactions WHERE signature = ?", (signature,))
    return cursor.fetchone() is not None


async def get_token_decimals(mint_address: str) -> int:
    """
    Получает количество минимальных единиц (decimals) для токена через API блокчейна Solana.
    :param mint_address: Адрес токена (mint address).
    :return: Количество минимальных единиц (decimals).
    """
    try:
        response = solana_client.get_token_supply(mint_address)
        if response.get("result") and response["result"]["value"]:
            decimals = response["result"]["value"]["decimals"]
            logger.info(f"Количество минимальных единиц для токена {mint_address}: {decimals}")
            return decimals
        else:
            logger.error(f"Не удалось получить информацию о токене {mint_address}")
            raise HTTPException(status_code=500, detail="Ошибка при получении информации о токене")
    except Exception as e:
        logger.error(f"Ошибка при запросе количества минимальных единиц для токена {mint_address}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при запросе данных токена")


async def check_transaction(signature: str, seller_wallet: str, expected_amount: int, currency: str, user_wallet: str) -> bool:
    """
    Проверяет статус платежа в Solana и возвращает результат.
    Добавлена проверка отправителя транзакции (fromPubkey) и динамическое получение decimals для токенов.
    """
    logger.info(f"Проверяем транзакцию {signature} для кошелька {seller_wallet} в валюте {currency}")

    # Проверяем, была ли транзакция уже обработана
    if is_transaction_processed(signature):
        logger.error(f"Транзакция {signature} уже была обработана")
        raise HTTPException(status_code=400, detail="Транзакция уже была обработана")

    # Проверяем, что валюта поддерживается
    if currency not in SUPPORTED_CURRENCIES:
        logger.error(f"Неподдерживаемая валюта: {currency}")
        raise HTTPException(status_code=400, detail=f"Неподдерживаемая валюта: {currency}")

    # Получаем decimals для выбранной валюты
    decimals = 9 if currency == "SOL" else await get_token_decimals(TOKEN_MINT_ADDRESSES[currency])
    multiplier = 10 ** decimals

    # Преобразуем строку в объект Signature
    try:
        sig_obj = Signature.from_string(signature)
    except ValueError:
        logger.error(f"Ошибка: Неверный формат подписи {signature}")
        return False

    for _ in range(10):  # 10 попыток проверки
        tx_data = solana_client.get_transaction(sig_obj, encoding="json")

        if tx_data and tx_data.value:
            # Проверяем, что транзакция направлена продавцу
            expected_seller_wallet = get_seller_wallet()
            transaction_message = tx_data.value.transaction.message
            recipient = transaction_message.account_keys[1].pubkey  # Получаем адрес получателя
            if recipient != expected_seller_wallet:
                logger.error(
                    f"Ошибка: Транзакция направлена не продавцу. Ожидалось: {expected_seller_wallet}, получено: {recipient}"
                )
                return False

            # Проверяем отправителя транзакции
            sender = transaction_message.account_keys[0].pubkey  # Получаем адрес отправителя
            if sender != user_wallet:
                logger.error(
                    f"Ошибка: Отправитель транзакции не совпадает с ожидаемым. Ожидалось: {user_wallet}, получено: {sender}"
                )
                raise HTTPException(status_code=400, detail="Отправитель транзакции не совпадает с ожидаемым")

            # Проверяем сумму транзакции
            amount = tx_data.value.transaction.message.instructions[0].data.lamports
            expected_amount_in_units = expected_amount * multiplier  # Преобразуем сумму в минимальные единицы
            if amount != expected_amount_in_units:
                logger.error(
                    f"Ошибка: Сумма транзакции не совпадает. Ожидалось: {expected_amount_in_units}, получено: {amount}"
                )
                raise HTTPException(status_code=400, detail="Сумма транзакции не совпадает с ожидаемой")

            # Проверяем, что транзакция выполнена не раньше чем 2 минуты назад
            block_time = tx_data.value.block_time
            if block_time:
                transaction_time = datetime.fromtimestamp(block_time, tz=timezone.utc)
                current_time = datetime.now(tz=timezone.utc)
                time_difference = (current_time - transaction_time).total_seconds()
                if time_difference > 120:  # 120 секунд = 2 минуты
                    logger.error(
                        f"Ошибка: Транзакция слишком старая. Время транзакции: {transaction_time}, текущее время: {current_time}"
                    )
                    return False

            # Сохраняем транзакцию в базе данных
            save_transaction(signature, seller_wallet, amount, currency)
            logger.info(f"Транзакция {signature} подтверждена! Slot {tx_data.value.slot}")
            return True

        await asyncio.sleep(2)

    logger.warning(f"Транзакция {signature} не найдена!")
    return False


async def process_payment(signature: str):
    """Обработка подтвержденного платежа"""
    logger.info(f"Выполняем действия после подтвержденной транзакции: {signature}")


# Инициализация HTTP Basic авторизации
security = HTTPBasic()

# Получение пароля из .env
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "default_password")


def verify_admin_password(credentials: HTTPBasicCredentials):
    """Проверяет пароль администратора"""
    if credentials.password != ADMIN_PASSWORD:
        logger.warning("Неверный пароль администратора")
        raise HTTPException(status_code=401, detail="Неверный пароль")


@app.get("/transactions", response_class=JSONResponse, dependencies=[Depends(RateLimiter(times=10, seconds=60))])
def get_all_transactions(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Возвращает JSON-файл со всеми транзакциями из базы данных.
    Ограничение: не более 10 запросов в минуту от одного клиента.
    Требуется HTTP Basic авторизация с паролем администратора.
    """
    # Проверяем пароль администратора
    verify_admin_password(credentials)

    try:
        # Извлекаем все транзакции из базы данных
        cursor.execute("SELECT id, signature, seller_wallet, amount, currency, timestamp FROM transactions")
        transactions = cursor.fetchall()

        # Преобразуем данные в список словарей
        transactions_list = [
            {
                "id": row[0],
                "signature": row[1],
                "seller_wallet": row[2],
                "amount": row[3],
                "currency": row[4],
                "timestamp": row[5],
            }
            for row in transactions
        ]

        # Возвращаем данные в формате JSON
        return JSONResponse(content=transactions_list)

    except Exception as e:
        logger.error(f"Ошибка при получении транзакций: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении транзакций")


# Эндпоинт для получения CSRF-токена
@app.get("/csrf-token")
def get_csrf_token():
    """Генерирует и возвращает CSRF-токен"""
    csrf_token = csrf_serializer.dumps({"csrf": "token"})
    logger.info("CSRF-токен успешно сгенерирован")
    return {"csrf_token": csrf_token}


# Проверка CSRF-токена
def verify_csrf_token(csrf_token: str):
    """Проверяет CSRF-токен"""
    try:
        csrf_data = csrf_serializer.loads(csrf_token, max_age=3600)  # Токен действителен 1 час
        if csrf_data.get("csrf") != "token":
            logger.error("Неверный CSRF-токен")
            raise HTTPException(status_code=403, detail="Неверный CSRF-токен")
    except Exception:
        logger.error("Неверный или истекший CSRF-токен")
        raise HTTPException(status_code=403, detail="Неверный или истекший CSRF-токен")


# Эндпоинт для получения кошелька продавца
@app.get("/get-seller-wallet")
def get_seller_wallet_endpoint():
    """Возвращает адрес кошелька продавца"""
    try:
        seller_wallet = get_seller_wallet()
        logger.info("Кошелек продавца успешно получен")
        return {"sellerWallet": seller_wallet}
    except ValueError as e:
        logger.error(f"Ошибка при получении кошелька продавца: {e}")
        return Response(content=str(e), status_code=500)


# Пример ограничения запросов для эндпоинта /pay
@app.post("/pay", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def pay(request: PaymentRequest):
    """
    Принимает транзакцию, проверяет ее и возвращает результат проверки.
    Ограничение: не более 5 запросов в минуту от одного клиента.
    """
    verify_csrf_token(request.csrf_token)  # Проверяем CSRF-токен

    # Проверяем, что кошелек продавца совпадает с указанным в .env
    expected_seller_wallet = get_seller_wallet()
    if request.seller_wallet != expected_seller_wallet:
        logger.error("Кошелек продавца не совпадает с ожидаемым")
        raise HTTPException(status_code=400, detail="Кошелек продавца не совпадает с ожидаемым")

    logger.info(f"Запуск проверки транзакции {request.tx_signature} в валюте {request.currency}")

    # Проверяем транзакцию
    try:
        result = await check_transaction(
            signature=request.tx_signature,
            seller_wallet=request.seller_wallet,
            expected_amount=1000000,  # Пример суммы
            currency=request.currency,
            user_wallet=request.seller_wallet,  # Передаем кошелек пользователя для проверки отправителя
        )
        if result:
            return {"message": "Транзакция успешно подтверждена"}
        else:
            raise HTTPException(status_code=400, detail="Транзакция не подтверждена или недействительна")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Ошибка при проверке транзакции: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при проверке транзакции")


@app.get("/ping")
def ping():
    """Проверка доступности сервера"""
    logger.info("Проверка доступности сервера (ping)")
    return {"message": "pong"}


from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Глобальный обработчик ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Обрабатывает все необработанные исключения"""
    logger.error(f"Необработанная ошибка: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Произошла внутренняя ошибка сервера. Пожалуйста, попробуйте позже."},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Обрабатывает исключения HTTPException"""
    logger.warning(f"HTTP ошибка: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обрабатывает ошибки валидации запросов"""
    logger.warning(f"Ошибка валидации: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


# Подключение к Redis для хранения данных о запросах
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

@app.on_event("startup")
async def startup():
    """
    Инициализация подключения к Redis при запуске приложения.
    """
    try:
        redis_client = redis.asyncio.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(redis_client)
        logger.info("FastAPI Limiter успешно инициализирован")
    except Exception as e:
        logger.error(f"Ошибка при подключении к Redis: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при инициализации лимитера запросов")

# Добавляем глобальное ограничение запросов
app.add_middleware(
    RateLimitMiddleware,
    authenticate=lambda request: request.client.host,  # Ограничение по IP клиента
    default_limits=["100/minute"],  # Ограничение: не более 100 запросов в минуту
)

# Запуск сервера
if __name__ == "__main__":
    import uvicorn

    logger.info("Запуск сервера...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
