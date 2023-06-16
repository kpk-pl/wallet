from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass, asdict, field
from bson.objectid import ObjectId
from flaskr import model
from decimal import Decimal
from typing import Dict, List, Optional
from collections import defaultdict

from .interp import interp
from .context import Context
from .parametrized import ParametrizedQuoting


class _PricingType:
    Quantity = 1
    Quote = 2
    Interest = 3

    @classmethod
    def create(cls, asset):
        if asset.pricing is None:
            return cls.Quantity
        elif isinstance(asset.pricing, model.AssetPricingQuotes):
            return cls.Quote
        elif isinstance(asset.pricing, model.AssetPricingParametrized):
            return cls.Interest
        else:
            raise NotImplementedError("Not implemented pricing type")


class _PricingBase(object):
    def __init__(self, ctx = None):
        super(_PricingBase, self).__init__()
        self._ctx = ctx if ctx is not None else Context()

        # Context for parametrized quoting, without startDate bound
        self._parameterCtx = Context(finalDate=self._ctx.finalDate,
                                     db=self._ctx._db,
                                     interpolate=False,
                                     keepOnlyFinalQuote=False)

        self._data = None  # Calculation context used for pricing that can also be copied to the debug dict


def groupOperationsById(operations: List[model.AssetOperation]) -> Dict[str|None, List[model.AssetOperation]]:
    operationsById = defaultdict(list)

    for operation in operations:
        operationsById[operation.orderId].append(operation)

    return operationsById


@dataclass
class _OpenPosition:
    quantity: Decimal
    operation: model.AssetOperation


def matchOrders(operations: List[model.AssetOperation]) -> Dict[str|None, List[_OpenPosition]]:
    operationsById = groupOperationsById(operations)
    result = defaultdict(list)

    for orderId, ops in operationsById.items():
        for op in ops:
            bucket = result[orderId]
            if op.type == model.AssetOperationType.buy:
                assert(isinstance(op.quantity, Decimal))
                bucket.append(_OpenPosition(op.quantity, op))
            elif op.type == model.AssetOperationType.receive:
                assert(isinstance(op.quantity, Decimal))
                bucket.append(_OpenPosition(op.quantity, op))
            elif op.type == model.AssetOperationType.sell:
                assert(isinstance(op.quantity, Decimal))
                remainingQuantity = op.quantity
                while remainingQuantity > 0:
                    buyOperation = bucket[0]
                    takenQuantity = min(buyOperation.quantity, remainingQuantity)
                    buyOperation.quantity -= takenQuantity
                    remainingQuantity -= takenQuantity
                    if buyOperation.quantity == 0:
                        del bucket[0]
            elif op.type == model.AssetOperationType.earning:
                # This is noop in this context as we are only pricing current market value of the asset
                pass

    return result


class Pricing(_PricingBase):
    @dataclass
    class CalcContext:
        type: _PricingType
        timerange: tuple[datetime, datetime]
        quantity: Optional[Decimal] = None
        netValue: Optional[Decimal] = None
        value: Optional[Decimal] = None
        operationsInScope: List[model.AssetOperation]|None = None
        pricingIds: List[ObjectId]|None = None
        quotes: dict[str, Decimal]|None = None

    def __init__(self, ctx = None):
        super(Pricing, self).__init__(ctx)

    def __call__(self, asset, debug=None):
        self._data = Pricing.CalcContext(
            type = _PricingType.create(asset),
            timerange = (self._ctx.startDate, self._ctx.finalDate)
        )

        if self._prepare(asset):
            if self._data.type is _PricingType.Quantity:
                self._byQuantity(asset)
            elif self._data.type is _PricingType.Quote:
                self._byQuote(asset)
            elif self._data.type is _PricingType.Interest:
                self._byInterest(asset)

        if isinstance(debug, dict):
            debug.update(asdict(self._data))

        return (self._data.netValue, self._data.quantity)

    def _prepare(self, asset):
        self._data.quotes = {}

        self._data.quantity = Decimal(0)
        self._data.netValue = Decimal(0)

        if not asset.operations:
            return False

        self._data.operationsInScope = [op for op in asset.operations if op.date <= self._ctx.finalDate]
        if not self._data.operationsInScope:
            return False

        self._data.pricingIds = []

        if isinstance(asset.pricing, model.AssetPricingQuotes):
            self._data.pricingIds.append(asset.pricing.quoteId)
        if asset.currency.quoteId is not None:
            self._data.pricingIds.append(asset.currency.quoteId)

        self._ctx.loadQuotes(self._data.pricingIds)

        return True

    def _netValueForCurrency(self, asset):
        if asset.currency.quoteId is None:
            return self._data.value

        currencyQuote = self._ctx.getFinalById(asset.currency.quoteId, asset.currency.name)
        if currencyQuote is None:
            return None

        assert self._data.quotes is not None
        self._data.quotes[str(asset.currency.quoteId)] = currencyQuote
        return self._data.value * currencyQuote

    def _byQuantity(self, asset):
        assert self._data.operationsInScope
        self._data.quantity = self._data.operationsInScope[-1].finalQuantity
        self._data.value = self._data.quantity
        self._data.netValue = self._netValueForCurrency(asset)

    def _byQuote(self, asset):
        assert self._data.operationsInScope
        self._data.quantity = self._data.operationsInScope[-1].finalQuantity
        if self._data.quantity == 0:
            return

        self._data.netValue = None

        quoteId = asset.pricing.quoteId
        # it might be possible in the future to pass currency name to getFinalById and in this way provide
        # pricing for assets with pricing in different currency as quoted
        # for now the currencies must match
        quote = self._ctx.getFinalById(quoteId)
        if quote is not None:
            self._data.quotes[str(quoteId)] = quote
            self._data.value = quote * self._data.quantity
            self._data.netValue = self._netValueForCurrency(asset)

    def _byInterest(self, asset:model.Asset):
        assert self._data.operationsInScope
        self._data.quantity = self._data.operationsInScope[-1].finalQuantity
        self._data.netValue = None

        operationsById = matchOrders(self._data.operationsInScope)

        self._data.value = Decimal(0)
        for openPosition in [p for pList in operationsById.values() for p in pList]:
            quoting = ParametrizedQuoting(asset.pricing, openPosition.operation.date, self._parameterCtx)
            keyPoints = quoting.getKeyPoints()
            if not keyPoints:
                return
            accumulatedValue = openPosition.operation.price * keyPoints[-1].multiplier
            assert(openPosition.operation.quantity is not None)
            self._data.value += accumulatedValue * (openPosition.quantity / openPosition.operation.quantity)

        self._data.netValue = self._data.value

    def priceAsset(self, asset, debug=None):
        return self.__call__(asset, debug)


@dataclass
class HistoryResult:
    timescale : List[datetime]
    value : List[Decimal] = field(default_factory=list)
    investedValue : List[Decimal]|None = None
    quantity : List[Decimal] = field(default_factory=list)
    profit : List[Decimal]|None = None

    def __init__(self, timescale):
        self.timescale = timescale

    @classmethod
    def null(cls, timescale, features):
        result = cls(timescale)
        result.value = [Decimal(0)] * len(result.timescale)
        result.quantity = [Decimal(0)] * len(result.timescale)
        result.profit = [Decimal(0)] * len(result.timescale) if features['profit'] else None
        result.investedValue = [Decimal(0)] * len(result.timescale) if features['investedValue'] else None
        return result

@dataclass
class _OpenPositionQuote:
    quote: Decimal
    quantity: Decimal
    operation: model.AssetOperation


class HistoryPricing(_PricingBase):
    @dataclass
    class CalcContext:
        type: _PricingType
        result: HistoryResult|None = None

    def __init__(self, ctx = None, features = {}):
        super(HistoryPricing, self).__init__(ctx)
        self._features = features
        if 'investedValue' not in self._features:
            self._features['investedValue'] = False
        if 'profit' not in self._features:
            self._features['profit'] = False

    def __call__(self, asset, profitsInfo=None, debug=None):
        self._data = HistoryPricing.CalcContext(
            type = _PricingType.create(asset)
        )

        if self._prepare(asset):
            assert self._data.result is not None
            if self._data.type is _PricingType.Quantity:
                self._data.result.value = self._priceAssetByQuantity(asset, self._data.result)
            elif self._data.type is _PricingType.Quote:
                self._data.result.value = self._priceAssetByQuote(asset, self._data.result)
            elif self._data.type is _PricingType.Interest:
                self._data.result.value = self._priceAssetByInterest(asset, self._data.result)

            if self._features['investedValue']:
                if profitsInfo is None:
                    raise RuntimeError("Cannot fulfill investedValue feature without profitsInfo")
                self._data.result.investedValue = self._getInvestedValue(asset.operations, profitsInfo)

            if self._features['profit']:
                if profitsInfo is None:
                    raise RuntimeError("Cannot fulfill profit feature without profitsInfo")
                self._data.result.profit = self._getAssetProfit(asset.operations, profitsInfo)

        if isinstance(debug, dict):
            debug.update(asdict(self._data))

        return self._data.result

    def _prepare(self, asset):
        if not asset.operations:
            self._data.result = HistoryResult.null(self._ctx.timeScale, self._features)
            return False

        idsToLoad = []
        if asset.pricing is not None and isinstance(asset.pricing, model.AssetPricingQuotes):
            idsToLoad.append(asset.pricing.quoteId)
        if asset.currency.quoteId is not None:
            idsToLoad.append(asset.currency.quoteId)

        self._ctx.loadQuotes(idsToLoad)

        self._data.result = HistoryResult(self._ctx.timeScale)
        self._data.result.quantity = self._getAssetQuantity(asset)
        return True

    def _getAssetQuantity(self, asset:model.Asset):
        ops = asset.operations

        operationIdx = 0
        quantity = Decimal(0)
        result = []

        for dateIdx in self._ctx.timeScale:
            # If this is the day the next operation happened, take new quantity
            while operationIdx < len(ops) and ops[operationIdx].date <= dateIdx:
                quantity = ops[operationIdx].finalQuantity
                operationIdx += 1

            result.append(quantity)

        return result

    def _getAssetProfit(self, operations:List[model.AssetOperation], profitsInfo):
        operationIdx = 0
        profit = Decimal(0)
        result = []

        for dateIdx in self._ctx.timeScale:
            # If this is the day the next operation happened, take new quantity
            while operationIdx < len(operations) and operations[operationIdx].date <= dateIdx:
                profit += profitsInfo.breakdown[operationIdx].netProfit
                operationIdx += 1

            result.append(profit)

        return result

    def _getInvestedValue(self, operations, profitsInfo):
        operationIdx = 0
        value = 0
        result = []

        for dateIdx in self._ctx.timeScale:
            # If this is the day the next operation happened, take new values
            while operationIdx < len(operations) and operations[operationIdx].date <= dateIdx:
                value = profitsInfo.breakdown[operationIdx].netInvestment
                operationIdx += 1

            result.append(value)

        return result

    def _priceAssetByQuantity(self, asset, result):
        currency = asset.currency

        value = [a for a in result.quantity]
        if currency.quoteId:
            value = [a * b for a, b in zip(value, self._ctx.getHistoricalById(currency.quoteId, currency.name))]

        return value

    def _priceAssetByQuote(self, asset, result):
        quoteId = asset.pricing.quoteId
        currency = asset.currency

        value = [a * b for a, b in zip(result.quantity, self._ctx.getHistoricalById(quoteId))]
        if currency.quoteId:
            value = [a * b for a, b in zip(value, self._ctx.getHistoricalById(currency.quoteId, currency.name))]

        return value

    def _priceAssetByInterest(self, asset:model.Asset, result):
        value = [Decimal(0.0)] * len(result.timescale)

        operationsById = groupOperationsById(asset.operations)
        for _, operations in operationsById.items():
            openPositionsQuotes : List[List[_OpenPositionQuote]] = []
            # for each day we need to save quotes, operation.quantity and remaining quantity

            for operation in operations:
                if operation.type == model.AssetOperationType.buy or operation.type == model.AssetOperationType.receive:
                    assert operation.quantity is not None
                    quoting = ParametrizedQuoting(asset.pricing, operation.date, self._parameterCtx)
                    keyPoints = quoting.getKeyPoints()
                    if not keyPoints:
                        continue

                    quoteHistory = list(map(lambda kp: model.QuoteHistoryItem(timestamp=kp.timestamp, quote=operation.price*kp.multiplier), keyPoints))
                    quotes = interp(quoteHistory, self._ctx.timeScale, leftFill = 0.0)
                    openPositionsQuotes.append([_OpenPositionQuote(quote=b.quote, quantity=operation.quantity, operation=operation) for b in quotes])
                elif operation.type == model.AssetOperationType.sell:
                    assert operation.quantity is not None
                    # from which index in result.timescale this SELL operation takes volume
                    firstIdx = next((idx for idx, date in enumerate(result.timescale) if date > operation.date), None)
                    if firstIdx is None:
                        continue

                    remainingQuantity = operation.quantity
                    for opq in openPositionsQuotes:
                        removedQuantity = min(remainingQuantity, opq[firstIdx].quantity)
                        if removedQuantity == 0:
                            continue
                        for item in opq[firstIdx:]:
                            item.quantity -= removedQuantity
                        remainingQuantity -= removedQuantity

                elif operation.type == model.AssetOperationType.earning:
                    # This is noop in this context as profits are already taken into account
                    pass

            for item in openPositionsQuotes:
                value = [v + i.quote*i.quantity/i.operation.quantity for i, v in zip(item, value)]

        return value
