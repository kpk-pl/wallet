from pydantic import BaseModel
from enum import Enum
from datetime import datetime
from decimal import Decimal
from typing import Optional


class AssetOperationType(str, Enum):
    buy = "BUY"
    sell = "SELL"
    receive = "RECEIVE"
    earning = "EARNING"


class AssetOperation(BaseModel):
    date: datetime
    type: AssetOperationType
    price: Decimal
    quantity: Optional[Decimal]
    finalQuantity: Optional[Decimal]
    provision: Decimal = Decimal(0)
    currencyConversion: Optional[Decimal]
    orderId: Optional[str]
