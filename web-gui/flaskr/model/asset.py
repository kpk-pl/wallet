from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional, List
from enum import Enum
from .types import PyObjectId
from .assetOperation import AssetOperation, AssetOperationType
from .assetPricing import AssetPricing, AssetPricingQuotes


class AssetCurrency(BaseModel):
    name: str
    quoteId: Optional[PyObjectId]


class AssetType(str, Enum):
    deposit = "Deposit"
    equity = "Equity"
    etf = "ETF"
    investmentFund = "Investment Fund"
    bond = "Bond"
    polishIndividualBonds = "Polish Individual Bonds"


class Asset(BaseModel):
    id: PyObjectId = Field(alias='_id')
    name: str
    ticker: Optional[str]
    currency: AssetCurrency
    institution: str
    type: AssetType
    category: str
    subcategory: Optional[str]
    region: Optional[str]
    link: Optional[HttpUrl]
    pricing: Optional[AssetPricing]
    operations: List[AssetOperation] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    trashed: bool = False
    hasOrderIds: bool = False

    @validator('operations', each_item=True)
    def check_no_receive_ops_for_deposit(cls, op, values):
        if 'type' in values and values['type'] == AssetType.deposit:
            if op.type == AssetOperationType.receive:
                raise ValueError("Invalid RECEIVE operation for Deposit asset")
        return op

    @validator('pricing')
    def check_no_pricing_for_deposits(cls, pricing, values):
        if 'type' in values and values['type'] == AssetType.deposit:
            if pricing is not None:
                raise ValueError("Pricing is not allowed for Deposit asset")

        return pricing

    @validator('operations', each_item=True)
    def check_quantity_equals_price_for_deposits(cls, op, values):
        if 'type' in values and values['type'] == AssetType.deposit:
            if op.quantity != op.price:
                raise ValueError("Quantity must be equal to price for Deposit asset operation")
        return op

    @validator('operations', each_item=True)
    def check_each_op_has_currency_conversion_when_asset_in_foreign_currency(cls, op, values):
        if 'pricing' in values and values['pricing'] is not None and isinstance(values['pricing'], AssetPricingQuotes):
            if op.currencyConversion is None:
                raise ValueError("Operation must have currency conversion specified for assets in foreign currency")
        return op

    @validator('hasOrderIds')
    def check_each_operation_has_orderId_when_required(cls, hasOrderIds, values):
        if hasOrderIds:
            for operation in values['operations']:
                if not operation.orderId:
                    raise ValueError("Each operation is required to have orderId when asset hasOrderIds")
        return hasOrderIds


