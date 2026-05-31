from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass, asdict, field
from bson.objectid import ObjectId
from flaskr import model
from flaskr import fifo
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

    def getLastPrice(self, quoteId:Optional[model.PyObjectId], currencyName:Optional[str] = None):
        return self._ctx.getFinalById(quoteId, currencyName) if quoteId is not None else None

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

        matched = fifo.match(self._data.operationsInScope, strict=False)

        self._data.value = Decimal(0)
        for lot in matched.lots:
            if lot.remaining == 0:
                continue
            quoting = ParametrizedQuoting(asset.pricing, lot.operation.date, self._parameterCtx)
            keyPoints = quoting.getKeyPoints()
            if not keyPoints:
                return
            accumulatedValue = lot.operation.price * keyPoints[-1].multiplier
            self._data.value += accumulatedValue * (lot.remaining / lot.openedQuantity)

        self._data.netValue = self._data.value

    def priceAsset(self, asset, debug=None):
        return self.__call__(asset, debug)


@dataclass
class HistoryResult:
    timescale : List[datetime]
    value : List[Decimal] = field(default_factory=list)
    provision : List[Decimal] = field(default_factory=list)
    investedValue : List[Decimal]|None = None
    quantity : List[Decimal] = field(default_factory=list)
    profit : List[Decimal]|None = None

    def __init__(self, timescale):
        self.timescale = timescale

    @classmethod
    def null(cls, timescale, features):
        result = cls(timescale)
        result.value = [Decimal(0)] * len(result.timescale)
        result.provision = [Decimal(0)] * len(result.timescale)
        result.quantity = [Decimal(0)] * len(result.timescale)
        result.profit = [Decimal(0)] * len(result.timescale) if features['profit'] else None
        result.investedValue = [Decimal(0)] * len(result.timescale) if features['investedValue'] else None
        return result

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

            self._data.result.provision = self._getProvision(asset.operations)

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

    def _getProvision(self, operations):
        operationIdx = 0
        provision = 0
        result = []

        for dateIdx in self._ctx.timeScale:
            # If this is the day the next operation happened, take new values
            while operationIdx < len(operations) and operations[operationIdx].date <= dateIdx:
                provision += operations[operationIdx].provision
                operationIdx += 1

            result.append(provision)

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

        # FIFO matching (per orderId, sells drawing down the oldest open lots) is shared with the
        # current-value pricing and the profits analyzer, so all three agree on which lot a sale
        # closed. Each open lot accrues parametrized interest on its remaining quantity over time.
        matched = fifo.match(asset.operations, strict=False)
        for lot in matched.lots:
            quoting = ParametrizedQuoting(asset.pricing, lot.operation.date, self._parameterCtx)
            keyPoints = quoting.getKeyPoints()
            if not keyPoints:
                continue

            quoteHistory = list(map(lambda kp: model.QuoteHistoryItem(timestamp=kp.timestamp, quote=lot.operation.price*kp.multiplier), keyPoints))
            quotes = interp(quoteHistory, self._ctx.timeScale, leftFill = 0.0)
            openQuantity = fifo.openQuantityOverTime(matched, lot, result.timescale)
            value = [v + q.quote * remaining / lot.openedQuantity
                     for q, remaining, v in zip(quotes, openQuantity, value)]

        return value
