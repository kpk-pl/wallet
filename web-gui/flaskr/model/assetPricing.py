from __future__ import annotations
from pydantic import BaseModel, PositiveInt, ConfigDict
from enum import Enum
from typing import List, Optional, Union
from decimal import Decimal
from .types import PyObjectId, BsonDecimal


class AssetPricingQuotes(BaseModel):
    quoteId: PyObjectId


class AssetPricingParametrizedLengthName(str, Enum):
    year = "year"
    month = "month"
    day = "day"


class AssetPricingParametrizedLength(BaseModel):
    count: PositiveInt
    name: AssetPricingParametrizedLengthName
    multiplier: PositiveInt = 1

    model_config = ConfigDict(use_enum_values=True)


class AssetPricingParametrizedProfitDistribution(str, Enum):
    distributing = "distributing"
    accumulating = "accumulating"


class AssetPricingParametrizedInterestItemFixed(BaseModel):
    percentage: BsonDecimal


class AssetPricingParametrizedInterestItemDerivedSampleChoose(str, Enum):
    first = "first"
    last = "last"


class AssetPricingParametrizedInterestItemDerivedSample(BaseModel):
    interval: AssetPricingParametrizedLengthName
    intervalOffset: int = 0
    choose: AssetPricingParametrizedInterestItemDerivedSampleChoose
    multiplier: BsonDecimal = Decimal(1)
    clampBelow: Optional[BsonDecimal] = None
    usePreviousWhenMissing: bool = False

    model_config = ConfigDict(use_enum_values=True)


class AssetPricingParametrizedInterestItemDerived(BaseModel):
    quoteId: PyObjectId
    sample: AssetPricingParametrizedInterestItemDerivedSample


class AssetPricingParametrizedInterestItem(BaseModel):
    fixed: Optional[AssetPricingParametrizedInterestItemFixed] = None
    derived: Optional[AssetPricingParametrizedInterestItemDerived] = None


class AssetPricingParametrized(BaseModel):
    length: AssetPricingParametrizedLength
    profitDistribution: AssetPricingParametrizedProfitDistribution
    interest: List[AssetPricingParametrizedInterestItem]

    model_config = ConfigDict(use_enum_values=True)


AssetPricing = Union[AssetPricingQuotes, AssetPricingParametrized]
