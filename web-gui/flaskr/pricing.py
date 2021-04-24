from datetime import datetime, timedelta
from flaskr import db


def _yearsBetween(lhs, rhs):
    yearDiff = rhs.year - lhs.year

    adjustedLhs = lhs.replace(year = rhs.year)
    if adjustedLhs > rhs:
        yearDiff -= 1

    return yearDiff


class PricingContext(object):
    def __init__(self, finalDate = datetime.now()):
        super(PricingContext, self).__init__()
        self.finalDate = finalDate
        self.finalQuotes = []

    def storedFinalIds(self):
        return set(q['_id'] for q in self.finalQuotes)

    def storedFinalNames(self):
        return set(q['name'] for q in self.finalQuotes)

    def loadFinalQuotes(self, ids, names):
        pipeline = [
            {'$match': {'$or': [
                {'_id': {'$in': list(set(ids) - self.storedFinalIds())}},
                {'name': {'$in': list(set(names) - self.storedFinalNames())}}
            ]}},
            {'$addFields': {
                'relevantQuotes': {'$filter': {
                        'input': '$quoteHistory',
                        'as': 'item',
                        'cond': {'$lte': ['$$item.timestamp', self.finalDate]}
                }}
            }},
            {'$project': {
                '_id': 1,
                'name': 1,
                'lastQuote': {'$last': '$relevantQuotes.quote'}
            }}
        ]
        self.finalQuotes.extend(list(db.get_db().quotes.aggregate(pipeline)))

    def getFinalById(self, quoteId):
        return next(x['lastQuote'] for x in self.finalQuotes if x['_id'] == quoteId)

    def getFinalByName(self, name):
        return next(x['lastQuote'] for x in self.finalQuotes if x['name'] == name)


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

    def _priceAssetByQuote(self, asset):
        if 'operations' not in asset or not asset['operations']:
            return 0.0

        quantity = asset['operations'][-1]['finalQuantity']
        if quantity == 0:
            return 0.0

        quoteId = asset['pricing']['quoteId']
        currencyName = asset['currency'] + 'PLN' if asset['currency'] != 'PLN' else None

        self._ctx.loadFinalQuotes(ids = [quoteId], names = [currencyName] if currencyName else [])

        value = quantity * self._ctx.getFinalById(quoteId)
        if currencyName:
            value *= self._ctx.getFinalByName(currencyName)

        return value

    def _priceAssetByInterest(self, asset):
        value = 0

        for operation in asset['operations']:
            if operation['type'] == 'BUY':
                value += self._priceAssetOperationByInterest(asset, operation)
            elif operation['type'] == 'SELL':
                raise NotImplementedError("Did not implement SELL operation")

        return value

    def _priceAssetOperationByInterest(self, asset, operation):
        pricing = asset['pricing']
        value = operation['price']

        if pricing['length']['periodName'] != 'year':
            raise NotImplementedError("Periods other than year are not implemented")

        passedPeriods = _yearsBetween(operation['date'], self._ctx.finalDate)
        if passedPeriods > 0:
            raise NotImplementedError("Did not implement calculating passed periods")

        interestDef = pricing['interest'][0]
        if 'derived' in interestDef:
            raise NotImplementedError("Did not implement calculating derived pricing")

        if 'fixed' in interestDef:
            percentage = interestDef['fixed']
            daysInLastPeriod = (self._ctx.finalDate - operation['date']).days
            value *= (1 + percentage * (daysInLastPeriod / 365))

        return value
