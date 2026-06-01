from __future__ import annotations
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from typing import Optional


class Quote(BaseModel):
    name: Optional[str] = None
    ticker: Optional[str] = None
    quote: Decimal
    timestamp: datetime
    currency: Optional[str] = None
    type: Optional[str] = None
