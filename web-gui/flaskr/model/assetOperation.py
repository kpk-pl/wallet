from pydantic import BaseModel, Field
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
    finalQuantity: Decimal
    provision: Decimal = Field(default_factory=Decimal)
    currencyConversion: Optional[Decimal]
    orderId: Optional[str]

    @property
    def unitPrice(self):
        result = self.price
        if self.quantity is not None:
            result = result / self.quantity
        return result

    @property
    def baseCurrencyPrice(self):
        result = self.price
        if self.currencyConversion is not None:
            result = result * self.currencyConversion
        return result

    @property
    def baseCurrencyUnitPrice(self):
        result = self.unitPrice
        if self.currencyConversion is not None:
            result = result * self.currencyConversion
        return result
