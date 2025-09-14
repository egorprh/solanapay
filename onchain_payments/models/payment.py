from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

class Payment(BaseModel):
    """
    Модель данных для криптовалютного платежа.
    
    Представляет полную информацию о платеже включая идентификатор,
    параметры сети и токена, адрес кошелька, статус и суммы.
    Используется для валидации данных и сериализации в JSON.
    
    Attributes:
        payment_id: Уникальный идентификатор платежа
        payment_network: Сеть блокчейна для платежа
        payment_token: Тип токена для платежа
        payment_address: Адрес кошелька для получения средств
        status: Текущий статус платежа
        payment_amount: Сумма полученных токенов
        outcome_amount: Эквивалент в USD
        created_at: Время создания платежа
        initial_balance: Начальный баланс кошелька
        
    Example:
        >>> payment = Payment(
        ...     payment_id="uuid-123",
        ...     payment_network="ethereum",
        ...     payment_token="eth",
        ...     payment_address="0x1234...",
        ...     initial_balance=0.0
        ... )
        >>> print(payment.status)
        pending
    """
    
    payment_id: str = Field(..., description="Unique payment identifier")
    payment_network: str = Field(..., description="Blockchain network (ethereum, polygon, arbitrum, optimism, solana)")
    payment_token: str = Field(..., description="Token type (eth, usdt, usdc, sol)")
    payment_address: str = Field(..., description="Wallet address for receiving payments")
    status: str = Field(default="pending", description="Payment status (pending, paid, cancelled)")
    payment_amount: Optional[float] = Field(None, description="Amount of tokens received")
    outcome_amount: Optional[float] = Field(None, description="Equivalent amount in USD")
    created_at: datetime = Field(default_factory=datetime.now, description="Payment creation timestamp")
    initial_balance: float = Field(..., description="Initial wallet balance when payment was created")
