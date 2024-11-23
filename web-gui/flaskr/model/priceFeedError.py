from pydantic import BaseModel
from datetime import datetime
from .types import PyObjectId


class PriceFeedError(BaseModel):
    pricingId: PyObjectId
    name: str
    timestamp: datetime
    trigger: str
    error: str
