from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from typing import Optional


class Quote(BaseModel):
    name: Optional[str]
    ticker: Optional[str]
    quote: Decimal
    timestamp: datetime
    currency: Optional[str]
    type: Optional[str]
