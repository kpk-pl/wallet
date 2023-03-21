from pydantic import BaseModel, PositiveInt
from enum import Enum
from typing import List, Optional, Union
from decimal import Decimal
from .types import PyObjectId


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

    class Config:
        use_enum_values = True

class AssetPricingParametrizedProfitDistribution(str, Enum):
    distributing = "distributing"
    accumulating = "accumulating"


class AssetPricingParametrizedInterestItemFixed(BaseModel):
    percentage: Decimal


class AssetPricingParametrizedInterestItemDerivedSampleChoose(str, Enum):
    first = "first"
    last = "last"


class AssetPricingParametrizedInterestItemDerivedSample(BaseModel):
    interval: AssetPricingParametrizedLengthName
    intervalOffset: int = 0
    choose: AssetPricingParametrizedInterestItemDerivedSampleChoose
    multiplier: Decimal = "1"
    clampBelow: Optional[Decimal]
    usePreviousWhenMissing: bool = False

    class Config:
        use_enum_values = True


class AssetPricingParametrizedInterestItemDerived(BaseModel):
    quoteId: PyObjectId
    sample: AssetPricingParametrizedInterestItemDerivedSample


class AssetPricingParametrizedInterestItem(BaseModel):
    fixed: Optional[AssetPricingParametrizedInterestItemFixed]
    derived: Optional[AssetPricingParametrizedInterestItemDerived]


class AssetPricingParametrized(BaseModel):
    length: AssetPricingParametrizedLength
    profitDistribution: AssetPricingParametrizedProfitDistribution
    interest: List[AssetPricingParametrizedInterestItem]

    class Config:
        use_enum_values = True


AssetPricing = Union[AssetPricingQuotes, AssetPricingParametrized]
