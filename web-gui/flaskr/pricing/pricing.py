from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass, asdict
from typing import Optional
from bson.objectid import ObjectId

from .interp import interp
from .context import Context
from .parametrized import ParametrizedQuoting


def _yearsBetween(lhs, rhs):
    return relativedelta(rhs, lhs).years


def _monthsBetween(lhs, rhs):
    delta = relativedelta(rhs, lhs)
    return delta.years * 12 + delta.months


class _PricingType:
    Quantity = 1
    Quote = 2
    Interest = 3

    @classmethod
    def create(cls, asset):
        if 'pricing' not in asset.keys():
            return cls.Quantity
        elif 'quoteId' in asset['pricing']:
            return cls.Quote
        elif 'interest' in asset['pricing']:
            return cls.Interest
        else:
            raise NotImplementedError("Not implemented pricing type")


class Pricing(object):
    @dataclass
    class CalcContext:
        type: _PricingType
        timerange: tuple[datetime, datetime]
        quantity: float = None
        netValue: float = None
        value: float = None
        operationsInScope: list[dict] = None
        pricingIds: list[ObjectId] = None
        quotes: dict[str, float] = None

    def __init__(self, ctx = None):
        super(Pricing, self).__init__()
        self._ctx = ctx if ctx is not None else Context()
        self._data = None  # Calculation context used for pricing that can also be copied to the debug dict

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
        self._data.quantity = 0
        self._data.netValue = 0.0

        if 'operations' not in asset or not asset['operations']:
            return False

        self._data.operationsInScope = [op for op in asset['operations'] if op['date'] <= self._ctx.finalDate]
        if not self._data.operationsInScope:
            return False

        return True

    def _byQuantity(self, asset):
        self._data.quantity = self._data.operationsInScope[-1]['finalQuantity']
        self._data.value = self._data.quantity

        if 'quoteId' in asset['currency']:
            currencyId = asset['currency']['quoteId']

            self._data.pricingIds = [currencyId]
            self._ctx.loadQuotes(self._data.pricingIds)
            currencyQuote = self._ctx.getFinalById(currencyId)

            self._data.quotes = { str(currencyId) : currencyQuote }
            self._data.netValue = self._data.value * currencyQuote
        else:
            self._data.netValue = self._data.value

    def _byQuote(self, asset):
        self._data.quantity = self._data.operationsInScope[-1]['finalQuantity']
        if self._data.quantity == 0:
            return

        self._data.netValue = None

        quoteId = asset['pricing']['quoteId']
        self._data.pricingIds = [quoteId]

        currencyId = None
        if 'quoteId' in asset['currency']:
            currencyId = asset['currency']['quoteId']
            self._data.pricingIds.append(currencyId)

        self._ctx.loadQuotes(self._data.pricingIds)
        self._data.quotes = {}

        quote = self._ctx.getFinalById(quoteId)
        if quote is not None:
            self._data.quotes[str(quoteId)] = quote
            self._data.value = quote * self._data.quantity
            self._data.netValue = self._data.value

            if currencyId:
                currencyQuote = self._ctx.getFinalById(currencyId)
                self._data.quotes[str(currencyId)] = currencyQuote
                self._data.netValue = self._data.value * currencyQuote

    def _byInterest(self, asset):
        self._data.quantity = self._data.operationsInScope[-1]['finalQuantity']

        self._data.value = 0
        for operation in self._data.operationsInScope:
            if operation['type'] == 'BUY':
                quoting = ParametrizedQuoting(asset['pricing'], operation['date'], self._ctx.finalDate)
                self._data.value += operation['price'] * quoting.getKeyPoints()[-1].multiplier
            else:
                raise NotImplementedError("Did not implement {} operation" % (operation['type']))

        self._data.netValue = self._data.value

    def priceAsset(self, asset, debug=None):
        return self.__call__(asset, debug)


@dataclass
class HistoryResult:
    timescale : list[datetime]
    value : list[float] = None
    investedValue : list[float] = None
    quantity : list[float] = None

    def __init__(self, timescale):
        self.timescale = timescale

    @classmethod
    def null(cls, timescale):
        result = self(timescale)
        result.value = [0.0] * len(result.timescale)
        result.investedValue = [0.0] * len(result.timescale)
        result.quantity = [0.0] * len(result.timescale)
        return result


class HistoryPricing(object):
    @dataclass
    class CalcContext:
        type: _PricingType
        result: HistoryResult = None


    def __init__(self, ctx = None, features = {}):
        super(HistoryPricing, self).__init__()
        self._ctx = ctx if ctx is not None else Context()
        self._features = features
        self._data = None  # Calculation context used for pricing that can also be copied to the debug dict

    def __call__(self, asset, debug=None):
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
                self._data.result.investedValue = self._getInvestedValue(asset)

        if isinstance(debug, dict):
            debug.update(asdict(self._data))

        return self._data.result

    def _prepare(self, asset):
        if 'operations' not in asset or not asset['operations']:
            self._data.result = HistoryResult.null(self._ctx.timeScale)
            return False

        self._data.result = HistoryResult(self._ctx.timeScale)
        self._data.result.quantity = self._getAssetQuantity(asset)
        return True

    def _getAssetQuantity(self, asset):
        ops = asset['operations']

        operationIdx = 0
        quantity = 0
        result = []

        for dateIdx in self._ctx.timeScale:
            # If this is the day the next operation happened, take new quantity
            while operationIdx < len(ops) and ops[operationIdx]['date'] <= dateIdx:
                quantity = ops[operationIdx]['finalQuantity']
                operationIdx += 1

            result.append(quantity)

        return result

    def _getInvestedValue(self, asset):
        ops = asset['operations']

        operationIdx = 0
        value = 0
        result = []

        for dateIdx in self._ctx.timeScale:
            # If this is the day the next operation happened, take new values
            while operationIdx < len(ops) and ops[operationIdx]['date'] <= dateIdx:
                value = ops[operationIdx]['finalQuantity'] * ops[operationIdx]['_stats']['averageNetPrice']
                operationIdx += 1

            result.append(value)

        return result

    def _priceAssetByQuantity(self, asset, result):
        currencyId = asset['currency']['quoteId'] if 'quoteId' in asset['currency'] else None

        value = [a for a in result.quantity]
        if currencyId:
            value = [a * b for a, b in zip(value, self._ctx.getHistoricalById(currencyId))]

        return value

    def _priceAssetByQuote(self, asset, result):
        quoteId = asset['pricing']['quoteId']
        currencyId = asset['currency']['quoteId'] if 'quoteId' in asset['currency'] else None

        self._ctx.loadQuotes(filter(None, [quoteId, currencyId]))

        value = [a * b for a, b in zip(result.quantity, self._ctx.getHistoricalById(quoteId))]
        if currencyId:
            value = [a * b for a, b in zip(value, self._ctx.getHistoricalById(currencyId))]

        return value

    def _priceAssetByInterest(self, asset, result):
        value = [0.0] * len(result.timescale)

        for operation in asset['operations']:
            if operation['type'] == 'BUY':
                quoting = ParametrizedQuoting(asset['pricing'], operation['date'], self._ctx.finalDate)
                quoteHistory = list(map(lambda kp: {'timestamp': kp.timestamp, 'quote': operation['price'] * kp.multiplier}, quoting.getKeyPoints()))
                quotes = interp(quoteHistory, self._ctx.timeScale, leftFill = 0.0)
                value = [a + b['quote'] for a, b in zip(value, quotes)]
            else:
                raise NotImplementedError("Did not implement {} operation" % (operation['type']))

        return value
