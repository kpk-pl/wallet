from datetime import datetime, timedelta, time
from flaskr import db


def _yearsBetween(lhs, rhs):
    yearDiff = rhs.year - lhs.year

    adjustedLhs = lhs.replace(year = rhs.year)
    if adjustedLhs > rhs:
        yearDiff -= 1

    return yearDiff


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
    def __init__(self, finalDate = datetime.now(), startDate = None):
        super(PricingContext, self).__init__()
        self.finalDate = finalDate
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
    def __init__(self, ctx = PricingContext()):
        super(Pricing, self).__init__()
        self._ctx = ctx

    def priceAsset(self, asset):
        if 'quoteId' in asset['pricing']:
            return self._priceAssetByQuote(asset)
        elif 'interest' in asset['pricing']:
            return self._priceAssetByInterest(asset)
        else:
            raise NotImplementedError("Not implemented pricing scheme")

    def priceAssetHistory(self, asset):
        if 'quoteId' in asset['pricing']:
            return self._priceAssetHistoryByQuote(asset)
        elif 'interest' in asset['pricing']:
            return self._priceAssetHistoryByInterest(asset)
        else:
            raise NotImplementedError("Not implemented pricing scheme")

    def _priceAssetByQuote(self, asset):
        if 'operations' not in asset or not asset['operations']:
            return 0.0, 0

        opsInScope = [op for op in asset['operations'] if op['date'] <= self._ctx.finalDate]
        if not opsInScope:
            return 0.0, 0

        quantity = opsInScope[-1]['finalQuantity']
        if quantity == 0:
            return 0.0, quantity

        ids = []

        quoteId = asset['pricing']['quoteId']
        ids.append(quoteId)

        currencyId = None
        if 'quoteId' in asset['currency']:
            currencyId = asset['currency']['quoteId']
            ids.append(currencyId)

        self._ctx.loadQuotes(ids)

        value = self._ctx.getFinalById(quoteId)
        if value is not None:
            value *= quantity
        if value is not None and currencyId:
            value *= self._ctx.getFinalById(currencyId)

        return value, quantity

    def _getNullPricingForAssetHistory(self):
        return {'t': self._ctx.timeScale,
                'q': [0.0] * len(self._ctx.timeScale),
                'y': [0.0] * len(self._ctx.timeScale)}

    def _priceAssetHistoryByQuote(self, asset):
        ops = asset['operations']
        if not ops:
            return self._getNullPricingForAssetHistory()

        result = {'t': self._ctx.timeScale, 'q': [], 'y': []}

        operationIdx = 0
        quantity = 0
        for dateIdx in result['t']:
            # If this is the day the next operation happened, take new quantity
            while operationIdx < len(ops) and ops[operationIdx]['date'] <= dateIdx:
                quantity = ops[operationIdx]['finalQuantity']
                operationIdx += 1

            result['q'].append(quantity)

        ids = []

        quoteId = asset['pricing']['quoteId']
        ids.append(quoteId)

        currencyId = None
        if 'quoteId' in asset['currency']:
            currencyId = asset['currency']['quoteId']
            ids.append(currencyId)

        self._ctx.loadQuotes(ids)

        result['y'] = [a * b for a, b in zip(result['q'], self._ctx.getHistoricalById(quoteId))]
        if currencyId:
            result['y'] = [a * b for a, b in zip(result['y'], self._ctx.getHistoricalById(currencyId))]

        return result

    def _priceAssetHistoryByInterest(self, asset):
        ops = asset['operations']
        if not ops:
            return self._getNullPricingForAssetHistory()

        result = {'t': self._ctx.timeScale, 'y': [0.0] * len(self._ctx.timeScale)}

        for operation in ops:
            if operation['type'] == 'BUY':
                quoteHistory = self._calculateQuoteHistoryForOperationByInterest(asset, operation)
                quotes = _interpolateLinear(quoteHistory, self._ctx.timeScale)
                result['y'] = [a + b['quote'] for a, b in zip(result['y'], quotes)]
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

        if pricing['length']['periodName'] != 'year':
            raise NotImplementedError("Periods other than year are not implemented")

        passedPeriods = _yearsBetween(operation['date'], self._ctx.finalDate)
        if passedPeriods > 0:
            raise NotImplementedError("Did not implement calculating passed periods")

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
