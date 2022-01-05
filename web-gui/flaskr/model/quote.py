from pydantic import BaseModel, Field
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
    _id: PyObjectId
    name: str
    unit: str
    url: str
    updateFrequency: str
    stooqSymbol: Optional[str]
    currencyPair: Optional[QuoteCurrencyPair]
    quoteHistory: List[QuoteHistoryItem] = Field(default_factory=list)

