import aiohttp
import logging
from typing import Optional


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Utils:
    """
    Утилитарный класс для работы с внешними API и вспомогательными функциями.
    
    Содержит методы для получения актуальных цен токенов через CoinGecko API
    и маппинга токенов на их идентификаторы в различных блокчейн-сетях.
    """
    
    @classmethod
    async def get_token_price(
        cls,
        token_str: str,
        network_str: str
    ) -> float:
        """
        Получение актуальной цены токена в USD через CoinGecko API.
        
        Асинхронно запрашивает текущую цену указанного токена в указанной сети
        через публичный API CoinGecko. Поддерживает основные криптовалюты
        и стабильные монеты.
        
        Args:
            token_str (str): Символ токена (eth, usdt, usdc, sol, matic)
            network_str (str): Название сети (ethereum, polygon, arbitrum, 
                              optimism, solana)
                              
        Returns:
            float: Цена токена в USD
            
        Raises:
            ValueError: Если токен или сеть не поддерживаются
            Exception: При ошибке HTTP запроса к CoinGecko API
            
        Example:
            >>> price = await Utils.get_token_price("eth", "ethereum")
            >>> print(f"ETH price: ${price}")
            ETH price: $2000.50
            
        Note:
            API CoinGecko имеет лимиты на количество запросов.
            Для продакшена рекомендуется использовать API ключ.
        """
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
    ) -> Optional[str]:
        """
        Получение идентификатора токена для CoinGecko API.
        
        Внутренний метод для маппинга символов токенов и сетей на
        соответствующие идентификаторы в CoinGecko API. Поддерживает
        основные криптовалюты и стабильные монеты в различных сетях.
        
        Args:
            token (str): Символ токена в нижнем регистре (eth, usdt, usdc, sol, matic)
            network (str): Название сети в нижнем регистре (ethereum, polygon, 
                          arbitrum, optimism, solana)
                          
        Returns:
            Optional[str]: Идентификатор токена в CoinGecko или None, если не найден
            
        Example:
            >>> token_id = Utils._get_coingecko_token_id("eth", "ethereum")
            >>> print(token_id)
            ethereum
            
            >>> token_id = Utils._get_coingecko_token_id("usdc", "polygon")
            >>> print(token_id)
            usd-coin
            
        Note:
            Метод возвращает None для неподдерживаемых комбинаций токен/сеть.
            Это используется для валидации перед запросом к API.
        """
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
