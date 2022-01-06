from datetime import datetime, time, timedelta
from pydantic import BaseModel, Field
from typing import List, Optional
from flaskr import db, model
from bson.objectid import ObjectId
from .interp import interp


def _dayByDay(start, finish):
    idx = datetime.combine(start.date(), time())
    oneDay = timedelta(days=1)
    result = []

    while idx <= finish:
        result.append(idx)
        idx += oneDay

    return result


class Context(object):
    class StorageType(BaseModel):
        id: model.PyObjectId = Field(alias='_id')
        currencyPair: Optional[model.QuoteCurrencyPair]
        quotes: List[model.QuoteHistoryItem] = Field(default_factory=list)


    def __init__(self, finalDate=None, startDate=None, interpolate=True, keepOnlyFinalQuote=True):
        super(Context, self).__init__()
        self.finalDate = finalDate if finalDate is not None else datetime.now()
        self.startDate = startDate
        self.interpolate = interpolate
        self.keepOnlyFinalQuote = keepOnlyFinalQuote
        self.timeScale = _dayByDay(startDate, finalDate) if startDate is not None and self.interpolate else []
        self.quotes = []

    def storedIds(self):
        return set(q.id for q in self.quotes)

    def loadQuotes(self, ids):
        if not isinstance(ids, list):
            ids = [ids]

        condition = {'$lte': ['$$item.timestamp', self.finalDate]}
        if self.startDate:
            condition = {'$and': [condition, {'$gte': ['$$item.timestamp', self.startDate]}]}
            projection = '$relevantQuotes'
        elif self.keepOnlyFinalQuote:
            projection = {'$slice': ['$relevantQuotes', -1]}
        else:
            projection = '$relevantQuotes'

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
            {'$project': {
                '_id': 1,
                'currencyPair': 1,
                'quotes': projection
            }}
        ]

        for item in db.get_db().quotes.aggregate(pipeline):
            if self.timeScale:
                item['quotes'] = interp(item['quotes'], self.timeScale)

            self.quotes.append(self.StorageType(**item))

    def _getById(self, quoteId):
        return next(x for x in self.quotes if x.id == quoteId)

    @staticmethod
    def _getCurrencyConversion(quoteEntry, required):
        if not quoteEntry.currencyPair or not required:
            return None

        if required == "GBP" and quoteEntry.currencyPair.destination == "GBX":
            return 100.0
        if required == "GBX" and quoteEntry.currencyPair.destination == "GBP":
            return 0.01

        return None

    @staticmethod
    def _returnSingle(quote, entry, currency):
        result = quote.quote

        multiplier = Context._getCurrencyConversion(entry, currency)
        if multiplier:
            result *= multiplier

        return result

    def getFinalById(self, quoteId, currency=None):
        entry = self._getById(quoteId)
        if not entry:
            return None

        return self._returnSingle(entry.quotes[-1], entry, currency)

    def getHistoricalById(self, quoteId, currency=None):
        entry = self._getById(quoteId)
        if not entry:
            return None

        result = [x.quote for x in entry.quotes]

        multiplier = self._getCurrencyConversion(entry, currency)
        if multiplier:
            result = [v*multiplier for v in result]

        return result

    def getPreviousById(self, quoteId, timestamp, currency=None):
        entry = self._getById(quoteId)
        if not entry:
            return None

        filtered = [q for q in entry.quotes if q.timestamp < timestamp]
        if not filtered:
            return None

        return self._returnSingle(filtered[-1], entry, currency)

    def getNextById(self, quoteId, timestamp, currency=None):
        entry = self._getById(quoteId)
        if not entry:
            return None

        filtered = [q for q in entry.quotes if q.timestamp > timestamp]
        if not filtered:
            return None

        return self._returnSingle(filtered[-1], entry, currency)
