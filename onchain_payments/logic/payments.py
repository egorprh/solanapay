import aiohttp
from typing import Any
from enum import Enum
from dataclasses import dataclass
from web3 import Web3
from src.core.config import settings
from src.onchain_payments.logic.wallet_manager import WalletManager
from src.onchain_payments.logic.utils import Utils, logger
from src.onchain_payments.models.payment import Payment
from src.onchain_payments.logic.database import db


class Network(Enum):
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    SOLANA = "solana"


class Token(Enum):
    ETH = "eth"
    USDT = "usdt"
    USDC = "usdc"
    SOL = "sol"


def erc20_abi_default():
    return [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "_to", "type": "address"},
                {"name": "_value", "type": "uint256"}
            ],
            "name": "transfer",
            "outputs": [
                {"name": "", "type": "bool"}
            ],
            "type": "function"
        }
    ]


def token_addresses_default():
    return {
        Network.POLYGON: {
            Token.USDT: "",
            Token.USDC: "",
        },
        Network.ARBITRUM: {
            Token.USDT: "",
            Token.USDC: ""
        },
        Network.OPTIMISM: {
            Token.USDT: "",
            Token.USDC: ""
        },
        Network.SOLANA: {
            Token.USDT: "",
            Token.USDC: ""
        }
    }


@dataclass
class Data:
    @staticmethod
    def erc20_abi():
        return erc20_abi_default()

    @staticmethod
    def token_addresses():
        return token_addresses_default()


class Payments:
    def __init__(self):
        logger.info("Initializing Payments class and connecting to networks")
        self.networks = {
            Network.POLYGON: Web3(Web3.HTTPProvider(settings.onchainpayments.POLYGON_NODE_URL)),
            Network.ARBITRUM: Web3(Web3.HTTPProvider(settings.onchainpayments.ARBITRUM_NODE_URL)),
            Network.OPTIMISM: Web3(Web3.HTTPProvider(settings.onchainpayments.OPTIMISM_NODE_URL)),
        }
        self.wallet_manager = WalletManager()

    async def create_payment(
        self,
        payment_id: str,
        payment_network: str,
        payment_token: str,
    ) -> dict[str, Any]:
        logger.info(f"Creating payment with ID: {payment_id}, network: {payment_network}, token: {payment_token}")
        network_str = payment_network.lower()
        token_str = payment_token.lower()
        payment_address = await self.wallet_manager.get_available_wallet(network_str)
        if not payment_address:
            logger.error("No available wallet address")
            raise Exception("No available wallet address")
        logger.info(f"Assigned payment address: {payment_address}")
        initial_balance = float(await self._get_current_balance(payment_address, token_str, network_str))
        logger.info(f"Initial balance for address {payment_address}: {initial_balance}")
        payment = Payment(
            payment_id=payment_id,
            payment_network=network_str,
            payment_token=token_str,
            payment_address=payment_address,
            status="pending",
            payment_amount=None,
            outcome_amount=None,
            initial_balance=initial_balance
        )
        logger.info(f"Payment object before insert: {payment.model_dump(mode="json")}")
        await db.payments.insert_one(payment.model_dump(mode="json"))
        logger.info(f"Payment created and stored in the database: {payment.model_dump(mode="json")}")
        return payment.model_dump(mode="json")

    async def process_payment(self, payment_id: str) -> dict[str, Any]:
        logger.info(f"Processing payment with ID: {payment_id}")
        payment_data = await db.payments.find_one({"payment_id": payment_id})
        if not payment_data:
            logger.error(f"Payment not found: {payment_id}")
            raise Exception("Payment not found")
        payment = Payment(**payment_data)
        logger.info(f"Found payment data: {payment_data}")
        if payment.status != "pending":
            logger.info(f"Payment is not pending: {payment.status}")
            return payment.model_dump(mode="json")
        payment_amount = await self.get_balance_change(
            payment.payment_address,
            payment.payment_token,
            payment.payment_network,
            payment.initial_balance
        )
        logger.info(f"Balance change: {payment_amount}")
        if payment_amount:
            token_price = await Utils.get_token_price(
                payment.payment_token, payment.payment_network
            )
            outcome_amount = payment_amount * token_price
            payment.status = "paid"
            payment.payment_amount = round(payment_amount, 8)
            payment.outcome_amount = round(outcome_amount, 2)
            logger.info(f"Updating payment status to \"paid\": {payment.model_dump(mode="json")}")
            await db.payments.update_one(
                {"payment_id": payment.payment_id},
                {"$set": payment.model_dump(mode="json")}
            )
            await self.wallet_manager.release_wallet(
                payment.payment_network,
                payment.payment_address
            )
        return payment.model_dump(mode="json")

    async def _get_current_balance(
        self,
        address: str,
        token_str: str,
        network_str: str
    ) -> float:
        logger.info(f"Getting current balance for address: {address}, token: {token_str}, network: {network_str}")

        if network_str in ["ethereum", "polygon", "arbitrum", "optimism"]:
            network = Network[network_str.upper()]
            w3 = self.networks[network]
            token = Token[token_str.upper()]

            if token == Token.ETH:
                balance = w3.eth.get_balance(Web3.to_checksum_address(address))
                balance_in_eth = float(Web3.from_wei(balance, "ether"))
                logger.info(f"ETH balance for address {address}: {balance_in_eth}")
                return balance_in_eth
            else:
                balance = await self._get_token_balance(w3, address, token, network)
                logger.info(f"Token balance for address {address}: {balance}")
                return balance
        elif network_str == "solana":
            token = Token[token_str.upper()]
            if token == Token.SOL:
                balance = await self._get_sol_balance(address)
                logger.info(f"SOL balance for address {address}: {balance}")
                return balance
            else:
                token_address = Data.token_addresses()[Network.SOLANA][token]
                balance = await self._get_spl_token_balance(address, token_address)
                logger.info(f"SPL token balance for address {address}: {balance}")
                return balance
        else:
            logger.error(f"Unsupported network: {network_str}")
            raise Exception(f"Unsupported network: {network_str}")

    async def _get_token_balance(
        self,
        w3: Web3,
        address: str,
        token: Token,
        network: Network
    ) -> float:
        logger.info(f"Fetching token balance for address: {address}, token: {token}, network: {network}")
        contract_address = Data.token_addresses()[network][token]
        token_contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=Data.erc20_abi()
        )
        balance = float(
            token_contract.functions.balanceOf(
                Web3.to_checksum_address(address)
            ).call()
        )
        decimals = token_contract.functions.decimals().call()
        readable_balance = balance / 10**decimals
        logger.info(f"Token balance: {readable_balance} {token}")
        return readable_balance

    async def _get_sol_balance(self, address: str) -> float:
        logger.info(f"Fetching SOL balance for address: {address}")
        async with aiohttp.ClientSession() as session:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [address]
            }
            async with session.post(
                settings.onchainpayments.SOLANA_NODE_URL, json=payload
            ) as response:
                if response.status == 200:
                    resp_json = await response.json()
                    sol_balance = float(resp_json["result"]["value"]) / 10e9
                    logger.info(f"SOL balance for address {address}: {sol_balance}")
                    return sol_balance
                else:
                    logger.error(f"Failed to get Solana balance: HTTP {response.status}")
                    raise Exception(f"Failed to get Solana balance: HTTP {response.status}")

    async def _get_spl_token_balance(
        self,
        address: str,
        token_address: str
    ) -> float:
        logger.info(f"Fetching SPL token balance for address: {address}, token_address: {token_address}")
        async with aiohttp.ClientSession() as session:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    address,
                    {"mint": token_address},
                    {"encoding": "jsonParsed"}
                ]
            }
            async with session.post(
                settings.onchainpayments.SOLANA_NODE_URL, json=payload
            ) as response:
                if response.status == 200:
                    resp_json = await response.json()
                    if resp_json["result"]["value"]:
                        balance = float(
                            resp_json["result"]["value"][0]["account"][
                                "data"
                            ]["parsed"]["info"]["tokenAmount"]["uiAmount"]
                        )
                        logger.info(f"SPL token balance: {balance}")
                        return balance
                    else:
                        logger.info("No SPL token balance found")
                        return 0.
                else:
                    logger.error(f"Failed to get SPL token balance: HTTP {response.status}")
                    raise Exception(f"Failed to get SPL token balance: HTTP {response.status}")

    async def get_balance_change(
        self,
        address: str,
        token_str: str,
        network_str: str,
        old_balance: float
    ) -> float:
        logger.info(f"Getting balance change for address: {address}, token: {token_str}, network: {network_str}")
        if network_str in ("ethereum", "polygon", "arbitrum", "optimism"):
            network = Network[network_str.upper()]
            w3 = self.networks[network]
            token = Token[token_str.upper()]
            return await self._get_token_balance_change(
                w3, address, token, network_str, old_balance
            )
        elif network_str == "solana":
            token = Token[token_str.upper()]
            if token == Token.SOL:
                return await self._get_sol_balance_change(address, old_balance)
            else:
                token_address = Data.token_addresses()[Network.SOLANA][token]
                return await self._get_spl_token_balance_change(address, token_address, old_balance)
        else:
            logger.error(f"Unsupported network: {network_str}")
            raise Exception(f"Unsupported network: {network_str}")

    async def _get_token_balance_change(
        self,
        w3: Web3,
        address: str,
        token: Token,
        network_str: str,
        old_balance: float
    ) -> float:
        logger.info(f"Getting token balance change for address: {address}, token: {token}")
        if token == Token.ETH:
            current_balance_wei = w3.eth.get_balance(Web3.to_checksum_address(address))
            current_balance = float(Web3.from_wei(current_balance_wei, "ether"))
            logger.info(f"Current ETH balance: {current_balance}")
            return current_balance - old_balance
        else:
            network_enum = Network[network_str.upper()]
            current_balance = await self._get_token_balance(w3, address, token, network_enum)
            logger.info(f"Current token balance: {current_balance}")
            return current_balance - old_balance

    async def _get_sol_balance_change(
        self,
        address: str,
        old_balance: float
    ) -> float:
        logger.info(f"Getting SOL balance change for address: {address}")
        current_balance = await self._get_sol_balance(address)
        logger.info(f"Current SOL balance: {current_balance}")
        return current_balance - old_balance

    async def _get_spl_token_balance_change(
        self,
        address: str,
        token_address: str,
        old_balance: float
    ) -> float:
        logger.info(f"Getting SPL token balance change for address: {address}, token_address: {token_address}")
        current_balance = await self._get_spl_token_balance(address, token_address)
        logger.info(f"Current SPL token balance: {current_balance}")
        return current_balance - old_balance

    async def cancel_payment(self, payment_id: str) -> dict[str, Any]:
        logger.info(f"Cancelling payment with ID: {payment_id}")
        payment_data = await db.payments.find_one({"payment_id": payment_id})
        if not payment_data:
            logger.error(f"Payment not found: {payment_id}")
            raise Exception("Payment not found")
        payment = Payment(**payment_data)
        logger.info(f"Found payment data: {payment_data}")
        if payment.status not in ["pending", "unpaid"]:
            logger.info(f"Cannot cancel payment with status: {payment.status}")
            return payment.model_dump(mode="json")
        payment.status = "cancelled"
        logger.info(f"Payment status updated to \"cancelled\": {payment.model_dump(mode="json")}")
        await db.payments.update_one(
            {"payment_id": payment.payment_id},
            {"$set": payment.model_dump(mode="json")}
        )
        await self.wallet_manager.release_wallet(
            payment.payment_network,
            payment.payment_address
        )
        return payment.model_dump(mode="json")

    async def _close_redis(self):
        logger.info("Closing redis connection")
        await self.wallet_manager.close()
