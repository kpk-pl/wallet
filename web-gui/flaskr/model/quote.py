from __future__ import annotations
from pydantic import BaseModel, Field, HttpUrl, root_validator
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from enum import Enum
from .types import PyObjectId


class QuoteHistoryItem(BaseModel):
    timestamp: datetime
    quote: Decimal


class QuoteCurrencyPair(BaseModel):
    destination: str
    source: str

    @root_validator(pre=True)
    def map_from_to_aliases(cls, values):
        if 'to' in values and 'destination' not in values:
            values['destination'] = values.pop('to')
        if 'from' in values and 'source' not in values:
            values['source'] = values.pop('from')
        return values


class QuoteUpdateFrequency(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class Quote(BaseModel):
    id: PyObjectId = Field(alias='_id')
    name: str
    unit: str
    ticker: Optional[str]
    urls: List[HttpUrl] = Field(default_factory=list)
    updateFrequency: QuoteUpdateFrequency
    trashed: bool = False
    currencyPair: Optional[QuoteCurrencyPair]
    quoteHistory: List[QuoteHistoryItem] = Field(default_factory=list)

    @root_validator(pre=True)
    def _coalesce_urls(cls, values):
        # Back-compat: documents (or payloads) carrying a scalar `url` and no
        # `urls` array are folded into the array form so `urls` stays the
        # single source of truth. Safe to keep even after the DB migration —
        # post-migration docs have `urls` and skip this branch.
        if not values.get('urls') and values.get('url'):
            values['urls'] = [values['url']]
        return values

    @property
    def url(self) -> Optional[HttpUrl]:
        """The primary source URL — first entry of `urls`. Kept as a property
        so existing callers/templates that read a single `url` keep working."""
        return self.urls[0] if self.urls else None

    @property
    def lastQuote(self) -> Optional[QuoteHistoryItem]:
        return self.quoteHistory[-1] if self.quoteHistory else None

