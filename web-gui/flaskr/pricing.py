from datetime import datetime, timedelta, time
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass
from flaskr import db


@dataclass
class ResultHistory:
    timescale : list
    value : list = None
    investedValue : list = None
    quantity : list = None

    def __init__(self, timescale):
        self.timescale = timescale

    def null(timescale):
        result = ResultHistory(timescale)
        result.value = [0.0] * len(result.timescale)
        result.investedValue = [0.0] * len(result.timescale)
        result.quantity = [0.0] * len(result.timescale)


def _yearsBetween(lhs, rhs):
    return relativedelta(rhs, lhs).years


def _monthsBetween(lhs, rhs):
    delta = relativedelta(rhs, lhs)
    return delta.years * 12 + delta.months


def _dayByDay(start, finish):
    idx = datetime.combine(start.date(), time())
    oneDay = timedelta(days=1)
    result = []

    while idx <= finish:
        result.append(idx)
        idx += oneDay

    return result


def _interpolateLinear(data, timeScale):
    assert len(data) > 0

    result = []
    quoteIdx = 0

    for dateIdx in timeScale:
        thisQuote = data[quoteIdx]
        while thisQuote['timestamp'] < dateIdx and quoteIdx < len(data) - 1:
            quoteIdx += 1
            thisQuote = data[quoteIdx]

        if quoteIdx == 0:
            result.append({'timestamp': dateIdx, 'quote': data[0]['quote']})
        elif thisQuote['timestamp'] < dateIdx:
            result.append({'timestamp': dateIdx, 'quote': data[-1]['quote']})
        else:
            prevQuote = data[quoteIdx-1]
            linearCoef = (dateIdx.timestamp() - prevQuote['timestamp'].timestamp())/(thisQuote['timestamp'].timestamp() - prevQuote['timestamp'].timestamp())
            linearQuote = linearCoef * (thisQuote['quote'] - prevQuote['quote']) + prevQuote['quote']
            result.append({'timestamp': dateIdx, 'quote': linearQuote})

    return result


class PricingContext(object):
    def __init__(self, finalDate = None, startDate = None):
        super(PricingContext, self).__init__()
        self.finalDate = finalDate if finalDate is not None else datetime.now()
        self.startDate = startDate
        self.timeScale = _dayByDay(startDate, finalDate) if startDate is not None else []
        self.quotes = []

    def storedIds(self):
        return set(q['_id'] for q in self.quotes)

    def storedNames(self):
        return set(q['name'] for q in self.quotes)

    def loadQuotes(self, ids):
        condition = {'$lte': ['$$item.timestamp', self.finalDate]}
        if self.startDate:
            condition = {'$and': [condition, {'$gte': ['$$item.timestamp', self.startDate]}]}
            projection = '$relevantQuotes'
        else:
            projection = {'$slice': ['$relevantQuotes', -1]}

        pipeline = [
            {'$match':
                {'_id': {'$in': list(set(ids) - self.storedIds())}},
            },
            {'$addFields': {
                'relevantQuotes': {'$filter': {
                        'input': '$quoteHistory',
                        'as': 'item',
                        'cond': condition
                }}
            }},
            {'$project': {'_id': 1, 'quotes': projection}}
        ]

        results = list(db.get_db().quotes.aggregate(pipeline))
        if not self.startDate:
            self.quotes.extend(results)
        else:
            for item in results:
                self._appendItemWithLinearQuotes(item)

    def _appendItemWithLinearQuotes(self, item):
        item['quotes'] = _interpolateLinear(item['quotes'], self.timeScale)
        self.quotes.append(item)

    def getFinalById(self, quoteId):
        quotesForId = [x['quotes'] for x in self.quotes if x['_id'] == quoteId]
        if not quotesForId or not quotesForId[-1]:
            return None

        return quotesForId[-1][0]['quote']

    def getHistoricalById(self, quoteId):
        quotes = next(x['quotes'] for x in self.quotes if x['_id'] == quoteId)
        return [x['quote'] for x in quotes]


class Pricing(object):
    def __init__(self, ctx = None):
        super(Pricing, self).__init__()
        self._ctx = ctx if ctx is not None else PricingContext()

    def priceAsset(self, asset, debug=None):
        self._data = {}
        self._data['finalDate'] = self._ctx.finalDate

        if 'quoteId' in asset['pricing']:
            self._priceAssetByQuote(asset)
            if isinstance(debug, dict):
                debug.update(self._data)
            return self._data['netValue'], self._data['quantity']
        elif 'interest' in asset['pricing']:
            return self._priceAssetByInterest(asset)
        else:
            raise NotImplementedError("Not implemented pricing scheme")

    def priceAssetHistory(self, asset):
        if not asset['operations']:
            return ResultHistory.null(self._ctx.timeScale)

        self._data = {}
        if 'quoteId' in asset['pricing']:
            return self._priceAssetHistoryByQuote(asset)
        elif 'interest' in asset['pricing']:
            return self._priceAssetHistoryByInterest(asset)
        else:
            raise NotImplementedError("Not implemented pricing scheme")

    def _priceAssetByQuote(self, asset):
        self._data['quantity'] = 0
        self._data['netValue'] = 0.0

        if 'operations' not in asset or not asset['operations']:
            return

        self._data['opsInScope'] = [op for op in asset['operations'] if op['date'] <= self._ctx.finalDate]
        if not self._data['opsInScope']:
            return

        self._data['quantity'] = self._data['opsInScope'][-1]['finalQuantity']
        if self._data['quantity'] == 0:
            return

        self._data['ids'] = []

        quoteId = asset['pricing']['quoteId']
        self._data['ids'].append(quoteId)

        currencyId = None
        if 'quoteId' in asset['currency']:
            currencyId = asset['currency']['quoteId']
            self._data['ids'].append(currencyId)

        self._ctx.loadQuotes(self._data['ids'])

        self._data['assetQuote'] = self._ctx.getFinalById(quoteId)
        if self._data['assetQuote'] is not None:
            self._data['value'] = self._data['assetQuote'] * self._data['quantity']

            if currencyId:
                self._data['currencyQuote'] = self._ctx.getFinalById(currencyId)
                self._data['netValue'] = self._data['value'] * self._data['currencyQuote']
            else:
                self._data['netValue'] = self._data['value']

    def _getAssetHistoryQuantity(self, asset):
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

    def _priceAssetHistoryByQuote(self, asset):
        result = ResultHistory(self._ctx.timeScale)
        result.quantity = self._getAssetHistoryQuantity(asset)

        quoteId = asset['pricing']['quoteId']
        currencyId = asset['currency']['quoteId'] if 'quoteId' in asset['currency'] else None

        self._ctx.loadQuotes(filter(None, [quoteId, currencyId]))

        result.value = [a * b for a, b in zip(result.quantity, self._ctx.getHistoricalById(quoteId))]
        if currencyId:
            result.value = [a * b for a, b in zip(result.value, self._ctx.getHistoricalById(currencyId))]

        return result

    def _priceAssetHistoryByInterest(self, asset):
        result = ResultHistory(self._ctx.timeScale)
        result.quantity = self._getAssetHistoryQuantity(asset)
        result.value = [0.0] * len(result.timescale)

        for operation in asset['operations']:
            if operation['type'] == 'BUY':
                quoteHistory = self._calculateQuoteHistoryForOperationByInterest(asset, operation)
                quotes = _interpolateLinear(quoteHistory, self._ctx.timeScale)
                result.value = [a + b['quote'] for a, b in zip(result.value, quotes)]
            elif operation['type'] == 'SELL':
                raise NotImplementedError("Did not implement SELL operation")

        return result

    def _priceAssetByInterest(self, asset):
        opsInScope = [op for op in asset['operations'] if op['date'] <= self._ctx.finalDate]
        if not opsInScope:
            return 0.0, 0

        value = 0
        for operation in opsInScope:
            if operation['type'] == 'BUY':
                value += self._calculateQuoteHistoryForOperationByInterest(asset, operation)[-1]['quote']
            elif operation['type'] == 'SELL':
                raise NotImplementedError("Did not implement SELL operation")

        return value, opsInScope[-1]['finalQuantity']

    def _calculateQuoteHistoryForOperationByInterest(self, asset, operation):
        pricing = asset['pricing']

        multiplier = pricing['length']['multiplier'] if 'multiplier' in pricing['length'] else 1

        if pricing['length']['name'] == 'year':
            passedPeriods = int(_yearsBetween(operation['date'], self._ctx.finalDate) / multiplier)
            if passedPeriods > 0:
                raise NotImplementedError("Did not implement calculating passed periods")
        elif pricing['length']['name'] == 'month':
            passedPeriods = int(_monthsBetween(operation['date'], self._ctx.finalDate) / multiplier)
            if passedPeriods > 0:
                raise NotImplementedError("Did not implement calculating passed periods")
        else:
            raise NotImplementedError("Periods other than year and month are not implemented")

        interestDef = pricing['interest'][0]
        if 'derived' in interestDef:
            raise NotImplementedError("Did not implement calculating derived pricing")

        result = [{'timestamp': operation['date'] - timedelta(seconds=1), 'quote': 0.0},
                  {'timestamp': operation['date'], 'quote': operation['price']}]

        if 'fixed' in interestDef:
            percentage = interestDef['fixed']
            daysInLastPeriod = (self._ctx.finalDate - operation['date']).days
            result.append({'timestamp': self._ctx.finalDate,
                           'quote': operation['price'] * (1 + percentage * (daysInLastPeriod / 365))})

        return result
