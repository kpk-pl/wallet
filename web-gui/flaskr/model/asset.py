from pydantic import BaseModel
from typing import List, Optional
from .types import PyObjectId


class AssetCurrency(BaseModel):
    name: str
    quoteId: Optional[PyObjectId]
