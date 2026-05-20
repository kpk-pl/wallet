from typing import Union

from .asset import Asset, AssetType, AssetCurrency
from .aggregated import AggregatedAsset
from .assetPricing import AssetPricing, AssetPricingQuotes, AssetPricingParametrized
from .assetOperation import AssetOperation, AssetOperationType
from .priceFeedError import PriceFeedError
from .quote import Quote, QuoteCurrencyPair, QuoteHistoryItem, QuoteUpdateFrequency
from .types import PyObjectId


WalletAsset = Union[Asset, AggregatedAsset]
