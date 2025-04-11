from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from solana.rpc.api import Client
from solders.signature import Signature  # 🔥 Добавляем правильный импорт
import asyncio

app = FastAPI()

# Разрешаем CORS для всех источников (для разработки)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Можно ограничить: ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],  # Разрешить все методы (POST, GET, OPTIONS и т.д.)
    allow_headers=["*"],  # Разрешить все заголовки
)

# Клиент Solana
solana_client = Client("https://api.devnet.solana.com")


# 📌 Модель для запроса
class PaymentRequest(BaseModel):
    seller_wallet: str
    tx_signature: str


async def check_transaction(signature: str, seller_wallet: str):
    """Проверяет статус платежа в Solana"""
    print(f"🔍 Проверяем транзакцию {signature} для кошелька {seller_wallet}")

    # 🔥 Преобразуем строку в объект Signature
    try:
        sig_obj = Signature.from_string(signature)
    except ValueError:
        print(f"❌ Ошибка: Неверный формат подписи {signature}")
        return

    for _ in range(10):  # 10 попыток проверки
        tx_data = solana_client.get_transaction(sig_obj, encoding="json")

        print(f"Ответ от Solana: {tx_data}")

        if tx_data and tx_data.value.slot:
            print(f"✅ Транзакция {signature} подтверждена! Slot {tx_data.value.slot}")
            await process_payment(signature)
            return

        await asyncio.sleep(2)

    print(f"⚠️ Транзакция {signature} не найдена!")


async def process_payment(signature: str):
    """Обработка подтвержденного платежа"""
    print(f"✅ Выполняем действия после подтвержденной транзакции: {signature}")


# 📌 Эндпоинт для обработки платежа
@app.post("/pay")
async def pay(request: PaymentRequest, background_tasks: BackgroundTasks):
    """Принимает транзакцию и запускает проверку"""
    background_tasks.add_task(check_transaction, request.tx_signature, request.seller_wallet)
    return {"message": "Проверка платежа запущена"}


@app.get("/ping")
def ping():
    return {"message": "pong"}


# 📌 Запуск сервера
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
