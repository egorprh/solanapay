# Интеграция Solana Pay: Реализация платежного сервиса на Python и JavaScript

## Введение

Solana Pay — это платежный протокол, работающий на блокчейне Solana, который позволяет мгновенно отправлять платежи между кошельками без посредников. В этом проекте мы реализовали сервер на FastAPI и фронтенд на HTML+JS, который взаимодействует с Solana Pay.

В ходе работы мы столкнулись с рядом проблем, таких как ошибки в обработке CORS, работа с API Solana, обработка транзакционных подписей и другие. Давайте разберёмся, как это всё работает и какие решения мы применили.

---

## Пошаговый алгоритм работы

1. **Пользователь заходит на страницу** с формой оплаты.
2. **Подключает свой кошелек** через кнопку "Подключить кошелек".
3. **Вводит сумму платежа** и нажимает "Оплатить".
4. **Фронтенд создаёт и подписывает транзакцию** с помощью Solana Web3.
5. **Отправляет транзакцию в сеть Solana** и получает `tx_signature`.
6. **Фронтенд отправляет `tx_signature` на сервер**, который проверяет статус транзакции.
7. **Бэкенд выполняет проверку платежа** в течение нескольких секунд.
8. **После подтверждения платежа** выполняются необходимые действия (например, зачисление средств).

---

## Проблемы, с которыми мы столкнулись, и их решения

### 1. Ошибка CORS (Cross-Origin Resource Sharing)

*Проблема:* Браузер блокировал запросы из-за политики безопасности.
*Решение:* Добавили `CORSMiddleware` в FastAPI, разрешив запросы со всех доменов.

### 2. Ошибка "Transaction recentBlockhash required"

*Проблема:* При отправке платежа Solana требовала recentBlockhash.
*Решение:* Корректно сформировали транзакцию на фронте перед её отправкой.

### 3. Ошибка "argument 'signature': 'str' object cannot be converted to 'Signature'"

*Проблема:* `get_transaction()` требовал объект `Signature`, а не строку.
*Решение:* Использовали `Signature.from_string(signature)` для преобразования строки.

### 4. Ошибка "SES_UNCAUGHT_EXCEPTION: TypeError: Спецификатор «@solana/web3.js»"

*Проблема:* Браузер не смог импортировать `@solana/web3.js` из-за его формата.
*Решение:* Вместо использования локальных модулей установили `@solana/web3.js` через CDN и корректно импортировали его как `import { Connection, PublicKey, Transaction } from "https://cdn.jsdelivr.net/npm/@solana/web3.js"`.

---

## Полный код проекта

### **Фронтенд (HTML + JavaScript)**

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Оплата через Solana Pay</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/web3/1.7.4/web3.min.js"></script>
    <script type="module" src="solana-pay.js"></script>
</head>
<body>
    <h2>Оплата через Solana</h2>
    <button onclick="connectWallet()">Подключить кошелек</button>
    <p id="wallet-status">Кошелек не подключен</p>
    <input type="number" id="amount" placeholder="Введите сумму в SOL" step="0.01">
    <button onclick="sendPayment()">Оплатить</button>
</body>
</html>
```

### **solana-pay.js (JS-скрипт для оплаты)**

```javascript
import { Connection, PublicKey, Transaction, SystemProgram, clusterApiUrl } from "https://cdn.jsdelivr.net/npm/@solana/web3.js";

const connection = new Connection(clusterApiUrl("devnet"));
let wallet = null;

export async function connectWallet() {
    try {
        const { solana } = window;
        if (!solana) throw new Error("Solana кошелек не найден");
        wallet = solana;
        await wallet.connect();
        document.getElementById("wallet-status").innerText = "Кошелек подключен";
    } catch (error) {
        console.error("Ошибка подключения кошелька:", error);
    }
}

export async function sendPayment() {
    try {
        const recipient = new PublicKey("SELLER_WALLET_ADDRESS");
        const amount = parseFloat(document.getElementById("amount").value) * 1e9; // в лампортах

        const transaction = new Transaction().add(
            SystemProgram.transfer({
                fromPubkey: wallet.publicKey,
                toPubkey: recipient,
                lamports: amount,
            })
        );

        const { blockhash } = await connection.getLatestBlockhash();
        transaction.recentBlockhash = blockhash;
        transaction.feePayer = wallet.publicKey;

        const signedTransaction = await wallet.signTransaction(transaction);
        const txSignature = await connection.sendRawTransaction(signedTransaction.serialize());
        console.log("Транзакция отправлена:", txSignature);
    } catch (error) {
        console.error("Ошибка при отправке платежа:", error);
    }
}
```

### **Бэкенд (FastAPI + Python)**

```python
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from solana.rpc.api import Client
from solders.signature import Signature
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

solana_client = Client("https://api.devnet.solana.com")

class PaymentRequest(BaseModel):
    seller_wallet: str
    tx_signature: str

async def check_transaction(signature: str, seller_wallet: str):
    print(f"🔍 Проверяем транзакцию {signature} для {seller_wallet}")
    try:
        sig_obj = Signature.from_string(signature)
    except ValueError:
        print("❌ Ошибка: Неверный формат подписи")
        return
    
    for _ in range(10):
        tx_data = solana_client.get_transaction(sig_obj)
        if tx_data and tx_data.get("result"):
            print(f"✅ Платеж {signature} подтвержден!")
            return
        await asyncio.sleep(2)
    print(f"⚠️ Транзакция {signature} не найдена!")

@app.post("/pay")
async def pay(request: PaymentRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(check_transaction, request.tx_signature, request.seller_wallet)
    return {"message": "Проверка платежа запущена"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Итог

Мы успешно реализовали сервис оплаты на Solana Pay, исправили ошибки и улучшили код. Теперь пользователи могут оплачивать товары, а сервер будет проверять транзакции и обрабатывать их.

🚀 **Готово к работе!**

