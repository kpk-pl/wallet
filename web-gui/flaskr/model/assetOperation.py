from __future__ import annotations
from pydantic import BaseModel, Field, validator
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
    # Always entered and stored in MAIN_CURRENCY (typically PLN), even when
    # the asset itself is denominated in a foreign currency. Do NOT multiply
    # by currencyConversion when summing — it would double-convert.
    provision: Decimal = Decimal(0)
    currencyConversion: Optional[Decimal]
    orderId: Optional[str]

    @validator('finalQuantity')
    def check_finalQuantity_non_negative(cls, finalQuantity):
        if finalQuantity < 0:
            raise ValueError(
                f"finalQuantity cannot be negative (got {finalQuantity})"
            )
        return finalQuantity

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
