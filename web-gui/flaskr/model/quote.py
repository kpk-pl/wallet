from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from enum import Enum
from .types import PyObjectId


class QuoteHistoryItem(BaseModel):
    timestamp: datetime
    quote: Decimal


class QuoteCurrencyPair(BaseModel):
    destination: str = Field(alias='to')
    source: str = Field(alias='from')


class QuoteUpdateFrequency(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class Quote(BaseModel):
    id: PyObjectId = Field(alias='_id')
    name: str
    unit: str
    ticker: Optional[str]
    url: HttpUrl
    updateFrequency: QuoteUpdateFrequency
    stooqSymbol: Optional[str]
    currencyPair: Optional[QuoteCurrencyPair]
    quoteHistory: List[QuoteHistoryItem] = Field(default_factory=list)

