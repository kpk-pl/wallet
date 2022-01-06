from pydantic import BaseModel
from typing import Optional
from .types import PyObjectId


class AssetCurrency(BaseModel):
    name: str
    quoteId: Optional[PyObjectId]
