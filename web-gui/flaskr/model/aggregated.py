from __future__ import annotations
from pydantic import BaseModel
from typing import List
from .asset import _AssetCore
from .types import PyObjectId


class AggregatedAsset(_AssetCore):
    ids: List[PyObjectId]
    institutions: List[str]
