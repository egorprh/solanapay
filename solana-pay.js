import { Connection, PublicKey, Transaction, SystemProgram, Token } from "https://esm.sh/@solana/web3.js";

// Устанавливаем RPC-узел с возможностью конфигурации
const RPC_URL = "https://api.devnet.solana.com"; // Ожидаемая сеть: Devnet
const EXPECTED_NETWORK = "devnet"; // Указываем ожидаемую сеть
const connection = new Connection(RPC_URL);

let wallet = null;
let csrfToken = null; // Переменная для хранения CSRF-токена

// Адреса токенов для Devnet (замените на Mainnet, если нужно)
const TOKEN_ADDRESSES = {
    SOL: null, // Для SOL используется SystemProgram.transfer
    USDC: "Es9vMFrzaCERz8r1t6k1y2kq9z9y9z9y9z9y9z9y9z9", // Пример адреса USDC
    USDT: "Es9vMFrzaCERz8r1t6k1y2kq9z9y9z9y9z9y9z9y9z9", // Пример адреса USDT
};

/**
 * Обработка ошибок: выводит сообщение пользователю и логирует ошибку.
 * @param {string} message - Сообщение для пользователя.
 * @param {Error} error - Объект ошибки.
 */
function handleError(message, error) {
    console.error(message, error);
    alert(message);
}

/**
 * Проверка сети кошелька.
 * @throws {Error} Если сеть кошелька не соответствует ожидаемой.
 */
async function checkNetwork() {
    const walletNetwork = wallet?.network || "unknown";
    if (walletNetwork.toLowerCase() !== EXPECTED_NETWORK) {
        throw new Error(`Кошелек подключен к неправильной сети: ${walletNetwork}. Ожидается: ${EXPECTED_NETWORK}.`);
    }
    console.log(`Кошелек подключен к правильной сети: ${walletNetwork}`);
}

/**
 * Получение CSRF-токена с сервера.
 * @throws {Error} Если не удалось получить CSRF-токен.
 */
async function fetchCsrfToken() {
    try {
        const response = await fetch("https://your-secure-server.com/csrf-token", {
            method: "GET",
            headers: { "Content-Type": "application/json" },
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Ошибка при получении CSRF-токена.");
        }

        const data = await response.json();
        csrfToken = data.csrf_token;
        console.log("CSRF-токен успешно получен:", csrfToken);
    } catch (error) {
        handleError("Не удалось получить CSRF-токен. Попробуйте позже.", error);
        throw error;
    }
}

/**
 * Получение адреса продавца с сервера.
 * @returns {PublicKey} Адрес кошелька продавца.
 * @throws {Error} Если не удалось получить адрес продавца.
 */
async function getSellerWallet() {
    try {
        const response = await fetch("https://your-secure-server.com/get-seller-wallet", {
            method: "GET",
            headers: { "Content-Type": "application/json" },
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Ошибка при получении адреса продавца.");
        }

        const data = await response.json();
        return new PublicKey(data.sellerWallet);
    } catch (error) {
        handleError("Не удалось получить адрес продавца. Попробуйте позже.", error);
        throw error;
    }
}

/**
 * Подключение кошелька.
 */
export async function connectWallet() {
    const availableWallets = [];

    // Проверяем наличие различных кошельков
    if (window.solana?.isPhantom) availableWallets.push({ name: "Phantom", wallet: window.solana });
    if (window.solflare) availableWallets.push({ name: "Solflare", wallet: window.solflare });
    if (window.sollet) availableWallets.push({ name: "Sollet", wallet: window.sollet });

    if (availableWallets.length === 0) {
        alert("Кошельки не найдены! Установите поддерживаемый кошелек, например Phantom или Solflare.");
        return;
    }

    const selectedWallet = availableWallets.length === 1
        ? availableWallets[0]
        : availableWallets[parseInt(prompt(
            `Доступны следующие кошельки:\n${availableWallets.map((w, i) => `${i + 1}. ${w.name}`).join("\n")}\nВведите номер кошелька для подключения:`
        ), 10) - 1];

    if (!selectedWallet) {
        alert("Неверный выбор кошелька!");
        return;
    }

    try {
        wallet = selectedWallet.wallet;
        await wallet.connect();
        document.getElementById("wallet-status").innerText = `Кошелек подключен: ${wallet.publicKey}`;
    } catch (error) {
        handleError("Не удалось подключить кошелек. Попробуйте снова.", error);
    }
}

/**
 * Отправка платежа.
 */
export async function sendPayment() {
    if (!wallet || !wallet.publicKey) {
        alert("Подключите кошелек!");
        return;
    }

    try {
        await checkNetwork(); // Проверяем сеть кошелька
    } catch (error) {
        handleError(error.message, error);
        return;
    }

    let sellerWallet;
    try {
        sellerWallet = await getSellerWallet();
    } catch {
        return; // Если не удалось получить адрес продавца, прерываем выполнение
    }

    const amountInput = document.getElementById("amount").value;
    const currency = document.getElementById("currency").value;

    // Валидация суммы и валюты
    if (!TOKEN_ADDRESSES[currency]) {
        alert("Выбрана некорректная валюта.");
        return;
    }

    const amount = parseFloat(amountInput) * (currency === "SOL" ? 1_000_000_000 : 1); // Для SOL переводим в лампорты
    if (isNaN(amount) || amount <= 0) {
        alert("Введите корректную сумму для оплаты.");
        return;
    }

    const transaction = new Transaction();

    if (currency === "SOL") {
        // Перевод SOL
        transaction.add(
            SystemProgram.transfer({
                fromPubkey: wallet.publicKey,
                toPubkey: sellerWallet,
                lamports: amount,
            })
        );
    } else {
        // Перевод токенов (USDC, USDT)
        const tokenAddress = new PublicKey(TOKEN_ADDRESSES[currency]);
        const tokenAccount = await connection.getTokenAccountsByOwner(wallet.publicKey, {
            mint: tokenAddress,
        });

        if (!tokenAccount.value.length) {
            alert(`У вас нет ${currency} на кошельке.`);
            return;
        }

        const sourceTokenAccount = tokenAccount.value[0].pubkey;

        transaction.add(
            Token.createTransferInstruction(
                Token.TOKEN_PROGRAM_ID,
                sourceTokenAccount,
                sellerWallet,
                wallet.publicKey,
                [],
                amount
            )
        );
    }

    try {
        const { blockhash } = await connection.getLatestBlockhash();
        transaction.recentBlockhash = blockhash;
        transaction.feePayer = wallet.publicKey;

        const signedTransaction = await wallet.signTransaction(transaction);
        const signature = await connection.sendRawTransaction(signedTransaction.serialize());

        console.log("Transaction Signature:", signature);
        alert("Оплата отправлена! Ожидаем подтверждения...");

        if (!csrfToken) await fetchCsrfToken();

        const response = await fetch("https://your-secure-server.com/pay", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken,
            },
            body: JSON.stringify({
                seller_wallet: sellerWallet.toBase58(),
                tx_signature: signature,
                timestamp: Date.now(),
                currency,
            }),
        });

        if (!response.ok) {
            const errorData = await response.json();
            const errorMessage = errorData.detail || "Неизвестная ошибка на сервере.";
            alert(`Ошибка: ${errorMessage}`);
            throw new Error(errorMessage);
        }

        const responseData = await response.json();
        alert(responseData.message || "Оплата успешно завершена!");
    } catch (error) {
        if (error instanceof Response) {
            try {
                const errorData = await error.json();
                alert(`Ошибка: ${errorData.detail || "Неизвестная ошибка на сервере."}`);
            } catch {
                alert("Произошла ошибка при обработке ответа от сервера.");
            }
        } else {
            handleError("Ошибка при отправке платежа.", error);
        }
    }
}

// Экспортируем функции для использования в HTML
window.connectWallet = connectWallet;
window.sendPayment = sendPayment;
