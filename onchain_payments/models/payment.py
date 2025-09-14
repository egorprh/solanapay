from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

class Payment(BaseModel):
    payment_id: str = Field(...)
    payment_network: str = Field(...)
    payment_token: str = Field(...)
    payment_address: str = Field(...)
    status: str = Field(default="pending")
    payment_amount: Optional[float] = None
    outcome_amount: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.now)
    initial_balance: float = Field(...)
