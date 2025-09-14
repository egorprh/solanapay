import aiohttp
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Utils:
    @classmethod
    async def get_token_price(
        cls,
        token_str: str,
        network_str: str
    ) -> float:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": "",
                "vs_currencies": "usd"
            }
            token_id = cls._get_coingecko_token_id(token_str, network_str)
            if not token_id:
                raise ValueError("Unsupported token/network")
            params["ids"] = token_id
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    resp_json = await resp.json()
                    price = resp_json.get(token_id, {}).get("usd")
                    if price:
                        return float(price)
                    else:
                        raise ValueError("Price not found")
                else:
                    raise Exception(f"Failed to get price from CoinGecko: status {resp.status}")

    @classmethod
    def _get_coingecko_token_id(
        cls,
        token: str,
        network: str
    ) -> str:
        mapping = {
            "solana": {
                "sol": "solana",
                "usdc": "usd-coin",
                "usdt": "tether"
            },
            "ethereum": {
                "eth": "ethereum",
                "usdc": "usd-coin",
                "usdt": "tether"
            },
            "polygon": {
                "matic": "matic-network",
                "usdc": "usd-coin",
                "usdt": "tether"
            },
            "arbitrum": {
                "eth": "ethereum",
                "usdc": "usd-coin",
                "usdt": "tether"
            },
            "optimism": {
                "eth": "ethereum",
                "usdc": "usd-coin",
                "usdt": "tether"
            },
        }
        network = network.lower()
        token = token.lower()
        return mapping.get(network, {}).get(token)
