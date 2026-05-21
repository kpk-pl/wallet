from __future__ import annotations
from pydantic import BaseModel, Field
from datetime import datetime
from .types import PyObjectId


class PriceFeedError(BaseModel):
    id: PyObjectId = Field(alias='_id')
    pricingId: PyObjectId
    name: str
    timestamp: datetime
    trigger: str
    error: str
