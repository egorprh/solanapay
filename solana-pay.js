import { Connection, PublicKey, Transaction, SystemProgram } from "https://esm.sh/@solana/web3.js";

const connection = new Connection("https://api.devnet.solana.com");

let wallet = null;

export async function connectWallet() {
    if (window.solana && window.solana.isPhantom) {
        wallet = window.solana;
        await wallet.connect();
        document.getElementById("wallet-status").innerText = `Кошелек подключен: ${wallet.publicKey}`;
    } else {
        alert("Установите кошелек Phantom!");
    }
}

export async function sendPayment() {
    if (!wallet || !wallet.publicKey) {
        alert("Подключите кошелек!");
        return;
    }

    const sellerWallet = new PublicKey("2kDfwYtSYiG18WJiTpsBKzBqAhVvDNhJjwvjw3nVsNN8");
    const amount = parseFloat(document.getElementById("amount").value) * 1_000_000_000;

    const transaction = new Transaction().add(
        SystemProgram.transfer({
            fromPubkey: wallet.publicKey,
            toPubkey: sellerWallet,
            lamports: amount,
        })
    );

    try {
        // Получаем актуальный recentBlockhash
        const { blockhash } = await connection.getLatestBlockhash();
        transaction.recentBlockhash = blockhash;
        transaction.feePayer = wallet.publicKey;

        // Подписываем и отправляем транзакцию
        const signedTransaction = await wallet.signTransaction(transaction);
        const signature = await connection.sendRawTransaction(signedTransaction.serialize());

        console.log("Transaction Signature:", signature);
        alert("Оплата отправлена! Ожидаем подтверждения...");

        await fetch("http://localhost:8000/pay", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ seller_wallet: sellerWallet.toBase58(), tx_signature: signature }),
        });
    } catch (error) {
        console.error("Ошибка при отправке платежа:", error);
        alert("Ошибка при отправке платежа!");
    }
}

window.connectWallet = connectWallet;
window.sendPayment = sendPayment;
