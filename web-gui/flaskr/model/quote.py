from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from datetime import datetime
from .types import PyObjectId


class QuoteHistoryItem(BaseModel):
    timestamp: datetime
    quote: float


class QuoteCurrencyPair(BaseModel):
    destination: str = Field(alias='to')
    source: str = Field(alias='from')


class Quote(BaseModel):
    id: PyObjectId = Field(alias='_id')
    name: str
    unit: str
    url: HttpUrl
    updateFrequency: str
    stooqSymbol: Optional[str]
    currencyPair: Optional[QuoteCurrencyPair]
    quoteHistory: List[QuoteHistoryItem] = Field(default_factory=list)

