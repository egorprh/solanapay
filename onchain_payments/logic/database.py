import motor.motor_asyncio
from src.core.config import settings

client = motor.motor_asyncio.AsyncIOMotorClient(
    f"mongodb://{settings.mongo.username}:{settings.mongo.password}@{settings.mongo.host}:{settings.mongo.port}"
)
db = client["onchain_payments"]