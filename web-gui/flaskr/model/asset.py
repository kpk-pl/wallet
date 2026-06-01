from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, ValidationInfo
from typing import Optional, List
from enum import Enum
from decimal import Decimal
from .types import PyObjectId, HttpUrlStr
from .assetOperation import AssetOperation, AssetOperationType
from .assetPricing import AssetPricing


class AssetCurrency(BaseModel):
    name: str
    quoteId: Optional[PyObjectId] = None


class AssetType(str, Enum):
    deposit = "Deposit"
    equity = "Equity"
    etf = "ETF"
    investmentFund = "Investment Fund"
    bond = "Bond"
    polishIndividualBonds = "Polish Individual Bonds"
    cryptocurrency = "Cryptocurrency"


class _AssetCore(BaseModel):
    name: str
    ticker: Optional[str] = None
    currency: AssetCurrency
    type: AssetType
    category: str
    subcategory: Optional[str] = None
    region: Optional[str] = None
    pricing: Optional[AssetPricing] = None
    operations: List[AssetOperation] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    hasOrderIds: bool = False

    @property
    def finalQuantity(self):
        if self.operations:
            return self.operations[-1].finalQuantity
        return 0

    @field_validator('operations')
    @classmethod
    def check_no_receive_ops_for_deposit(cls, operations, info: ValidationInfo):
        if info.data.get('type') == AssetType.deposit:
            for op in operations:
                if op.type == AssetOperationType.receive:
                    raise ValueError("Invalid RECEIVE operation for Deposit asset")
        return operations

    @field_validator('pricing')
    @classmethod
    def check_no_pricing_for_deposits(cls, pricing, info: ValidationInfo):
        if info.data.get('type') == AssetType.deposit:
            if pricing is not None:
                raise ValueError("Pricing is not allowed for Deposit asset")

        return pricing

    @field_validator('operations')
    @classmethod
    def check_quantity_equals_price_for_deposits(cls, operations, info: ValidationInfo):
        if info.data.get('type') == AssetType.deposit:
            for op in operations:
                if op.quantity != op.price:
                    raise ValueError("Quantity must be equal to price for Deposit asset operation")
        return operations

    @field_validator('operations')
    @classmethod
    def check_each_op_has_currency_conversion_when_asset_in_foreign_currency(cls, operations, info: ValidationInfo):
        currency = info.data.get('currency')
        if currency is not None and currency.quoteId is not None:
            for op in operations:
                if op.currencyConversion is None:
                    raise ValueError("Operation must have currency conversion specified for assets in foreign currency")
        return operations

    @field_validator('operations')
    @classmethod
    def check_operations_sorted_by_date(cls, operations):
        for prev, curr in zip(operations, operations[1:]):
            if curr.date < prev.date:
                raise ValueError(
                    f"Operations must be ordered by date ascending; "
                    f"got {curr.date.isoformat()} after {prev.date.isoformat()}"
                )
        return operations

    @field_validator('operations')
    @classmethod
    def check_quantity_and_final_quantity_is_consistent(cls, operations, info: ValidationInfo):
        if 'type' not in info.data:
            raise ValueError("Cannot check quantity consistency because asset type is unknown")

        expectedFinalQuantity = Decimal(0)
        for op in operations:
            if op.type == AssetOperationType.buy:
                expectedFinalQuantity += op.quantity
            elif op.type == AssetOperationType.sell:
                expectedFinalQuantity -= op.quantity
            elif op.type == AssetOperationType.receive:
                # a RECEIVE is essentially a BUY with a price 0
                expectedFinalQuantity += op.quantity
            elif op.type == AssetOperationType.earning:
                # EARNING changes quantity only for deposits
                if info.data['type'] == AssetType.deposit:
                    expectedFinalQuantity += op.quantity

            if expectedFinalQuantity < 0:
                raise ValueError("Operation resulted in expected final quantity less than zero")
            if op.finalQuantity != expectedFinalQuantity:
                raise ValueError("Inconsistency between operation quantity and expected final quantity")

        return operations


    @field_validator('hasOrderIds')
    @classmethod
    def check_each_operation_has_orderId_when_required(cls, hasOrderIds, info: ValidationInfo):
        if hasOrderIds:
            for operation in info.data.get('operations', []):
                if not operation.orderId:
                    raise ValueError("Each operation is required to have orderId when asset hasOrderIds")
        return hasOrderIds


class Asset(_AssetCore):
    id: PyObjectId = Field(alias='_id')
    institution: str
    link: Optional[HttpUrlStr] = None
    trashed: bool = False
