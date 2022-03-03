from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from .types import PyObjectId
from .assetOperation import AssetOperation
from .assetPricing import AssetPricing


class AssetCurrency(BaseModel):
    name: str
    quoteId: Optional[PyObjectId]


class Asset(BaseModel):
    id: PyObjectId = Field(alias='_id')
    name: str
    ticker: Optional[str]
    currency: AssetCurrency
    institution: str
    type: str
    category: str
    subcategory: Optional[str]
    region: Optional[str]
    link: Optional[HttpUrl]
    operations: List[AssetOperation] = Field(default_factory=list)
    pricing: Optional[AssetPricing]
    labels: List[str] = Field(default_factory=list)
    trashed: bool = False
    hasOrderIds: bool = False
