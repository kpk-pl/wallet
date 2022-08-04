from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass, asdict
from bson.objectid import ObjectId
from flaskr import model
from decimal import Decimal
from typing import List

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
        quantity: Decimal = None
        netValue: Decimal = None
        value: Decimal = None
        operationsInScope: List[model.AssetOperation] = None
        pricingIds: List[ObjectId] = None
        quotes: dict[str, Decimal] = None

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

        self._data.quotes[str(asset.currency.quoteId)] = currencyQuote
        return self._data.value * currencyQuote

    def _byQuantity(self, asset):
        self._data.quantity = self._data.operationsInScope[-1].finalQuantity
        self._data.value = self._data.quantity
        self._data.netValue = self._netValueForCurrency(asset)

    def _byQuote(self, asset):
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
        self._data.quantity = self._data.operationsInScope[-1].finalQuantity
        self._data.netValue = None

        self._data.value = Decimal(0)
        for operation in self._data.operationsInScope:
            if operation.type == model.AssetOperationType.buy:
                quoting = ParametrizedQuoting(asset.pricing, operation.date, self._parameterCtx)
                keyPoints = quoting.getKeyPoints()
                if not keyPoints:
                    return
                accumulatedValue = operation.price * keyPoints[-1].multiplier
                self._data.value += accumulatedValue
            elif operation.type == model.AssetOperationType.earning:
                # This is noop in this context as we are only pricing current market value of the asset
                pass
            else:
                raise NotImplementedError("Did not implement {} operation" % (operation.type))

        self._data.netValue = self._data.value

    def priceAsset(self, asset, debug=None):
        return self.__call__(asset, debug)


@dataclass
class HistoryResult:
    timescale : List[datetime]
    value : List[float] = None
    investedValue : List[float] = None
    quantity : List[float] = None
    profit : List[Decimal] = None

    def __init__(self, timescale):
        self.timescale = timescale

    @classmethod
    def null(cls, timescale):
        result = cls(timescale)
        result.value = [0.0] * len(result.timescale)
        result.investedValue = [0.0] * len(result.timescale)
        result.quantity = [0.0] * len(result.timescale)
        result.profit = [Decimal(0)] * len(result.timescale)
        return result


class HistoryPricing(_PricingBase):
    @dataclass
    class CalcContext:
        type: _PricingType
        result: HistoryResult = None


    def __init__(self, ctx = None, features = {}):
        super(HistoryPricing, self).__init__(ctx)
        self._features = features

    def __call__(self, asset, profitsInfo=None, debug=None):
        self._data = HistoryPricing.CalcContext(
            type = _PricingType.create(asset)
        )

        if self._prepare(asset):
            if self._data.type is _PricingType.Quantity:
                self._data.result.value = self._priceAssetByQuantity(asset, self._data.result)
            elif self._data.type is _PricingType.Quote:
                self._data.result.value = self._priceAssetByQuote(asset, self._data.result)
            elif self._data.type is _PricingType.Interest:
                self._data.result.value = self._priceAssetByInterest(asset, self._data.result)

            if 'investedValue' in self._features and self._features['investedValue']:
                if profitsInfo is None:
                    raise RuntimeError("Cannot fultill investedValue feature without profitsInfo")
                self._data.result.investedValue = self._getInvestedValue(asset.operations, profitsInfo)

        if isinstance(debug, dict):
            debug.update(asdict(self._data))

        return self._data.result

    def _prepare(self, asset):
        if not asset.operations:
            self._data.result = HistoryResult.null(self._ctx.timeScale)
            return False

        self._data.result = HistoryResult(self._ctx.timeScale)
        self._data.result.quantity = self._getAssetQuantity(asset)
        self._data.result.profit = self._getAssetProfit(asset)
        return True

    def _getAssetQuantity(self, asset:model.Asset):
        ops = asset.operations

        operationIdx = 0
        quantity = 0
        result = []

        for dateIdx in self._ctx.timeScale:
            # If this is the day the next operation happened, take new quantity
            while operationIdx < len(ops) and ops[operationIdx].date <= dateIdx:
                quantity = ops[operationIdx].finalQuantity
                operationIdx += 1

            result.append(quantity)

        return result

    def _getAssetProfit(self, asset:model.Asset):
        ops = asset.operations

        operationIdx = 0
        profit = Decimal(0)
        result = []

        for dateIdx in self._ctx.timeScale:
            # If this is the day the next operation happened, take new quantity
            while operationIdx < len(ops) and ops[operationIdx].date <= dateIdx:
                profit += ops[operationIdx].price
                operationIdx += 1

            result.append(profit)

    def _getInvestedValue(self, operations, profitsInfo):
        operationIdx = 0
        value = 0
        result = []

        for dateIdx in self._ctx.timeScale:
            # If this is the day the next operation happened, take new values
            while operationIdx < len(operations) and operations[operationIdx].date <= dateIdx:
                value = profitsInfo.breakdown[operationIdx].netInvestment
                # value = operations[operationIdx].finalQuantity * Decimal(profitsInfo['operations'][operationIdx]['_stats']['averageNetPrice'])
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

        ids = [quoteId]
        if currency.quoteId:
            ids.append(currency.quoteId)
        self._ctx.loadQuotes(ids)

        value = [a * b for a, b in zip(result.quantity, self._ctx.getHistoricalById(quoteId))]
        if currency.quoteId:
            value = [a * b for a, b in zip(value, self._ctx.getHistoricalById(currency.quoteId, currency.name))]

        return value

    def _priceAssetByInterest(self, asset:model.Asset, result):
        value = [Decimal(0.0)] * len(result.timescale)

        for operation in asset.operations:
            if operation.type == model.AssetOperationType.buy:
                quoting = ParametrizedQuoting(asset.pricing, operation.date, self._parameterCtx)
                keyPoints = quoting.getKeyPoints()
                if not keyPoints:
                    continue

                quoteHistory = list(map(lambda kp: model.QuoteHistoryItem(timestamp=kp.timestamp, quote=operation.price*kp.multiplier), keyPoints))
                quotes = interp(quoteHistory, self._ctx.timeScale, leftFill = 0.0)
                value = [a + b.quote for a, b in zip(value, quotes)]
            elif operation.type == model.AssetOperationType.earning:
                # This is noop in this context as profits are already taken into account
                pass
            else:
                raise NotImplementedError("Did not implement {} operation" % (operation.type))

        return value
