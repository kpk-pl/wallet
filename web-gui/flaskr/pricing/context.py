from datetime import datetime, time, timedelta
from pydantic import BaseModel, Field
from decimal import Decimal
from typing import List, Optional
from flaskr import model
from bson.objectid import ObjectId
from .interp import interp


def _dayByDay(start, finish, alignTimescale = None):
    idx = datetime.combine(start.date(), alignTimescale) if alignTimescale else start
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


    def __init__(self, finalDate=None, startDate=None, interpolate=True, keepOnlyFinalQuote=True, alignTimescale = None, db=None):
        super(Context, self).__init__()
        self.finalDate = finalDate if finalDate is not None else datetime.now()
        self.startDate = startDate
        self.interpolate = interpolate
        self.keepOnlyFinalQuote = keepOnlyFinalQuote
        self._db = db

        self.timeScale = _dayByDay(startDate, finalDate, alignTimescale) if startDate is not None and self.interpolate else []
        self.quotes = []

    def _getDB(self):
        if self._db:
            return self._db

        from flaskr import db
        return db.get_db()

    def storedIds(self):
        return set(q.id for q in self.quotes)

    def loadQuotes(self, ids):
        if not isinstance(ids, list):
            ids = [ids]

        condition = {'$lte': ['$$item.timestamp', self.finalDate]}
        if self.startDate:
            condition = {'$and': [condition, {'$gte': ['$$item.timestamp', self.startDate]}]}
            projection = {'$ifNull': ['$relevantQuotes', []]}
        elif self.keepOnlyFinalQuote:
            projection = {'$ifNull': [{'$slice': ['$relevantQuotes', -1]}, []]}
        else:
            projection = {'$ifNull': ['$relevantQuotes', []]}

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
            # {'$set': {
                # 'quotes': {
                    # '$map': {
                        # 'input': "$quotes",
                        # 'as': "q",
                        # 'in': {
                            # "timestamp": "$$q.timestamp",
                            # "quote": { '$toDecimal': "$$q.quote" }
                        # }
                    # }
                # }
            # }}
        ]

        for item in self._getDB().quotes.aggregate(pipeline):
            quoteItem = self.StorageType(**item)

            if self.timeScale:
                if quoteItem.quotes:
                    quoteItem.quotes = interp(quoteItem.quotes, self.timeScale)

            self.quotes.append(quoteItem)

    def _getById(self, quoteId):
        return next((x for x in self.quotes if x.id == quoteId), None)

    @staticmethod
    def _getCurrencyConversion(quoteEntry, required):
        if not quoteEntry.currencyPair or not required:
            return None

        if required == "GBP" and quoteEntry.currencyPair.destination == "GBX":
            return Decimal(100)
        if required == "GBX" and quoteEntry.currencyPair.destination == "GBP":
            return Decimal("0.01")

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
        if not entry or not entry.quotes:
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

    def getPreviousById(self, quoteId, timestamp, currency=None, withTimestamp=False):
        entry = self._getById(quoteId)
        if not entry:
            return None if not withTimestamp else (None, None)

        filtered = [q for q in entry.quotes if q.timestamp < timestamp]
        if not filtered:
            return None if not withTimestamp else (None, None)

        if not withTimestamp:
            return self._returnSingle(filtered[-1], entry, currency)
        else:
            return self._returnSingle(filtered[-1], entry, currency), filtered[-1].timestamp

    def getNextById(self, quoteId, timestamp, currency=None, withTimestamp=False):
        entry = self._getById(quoteId)
        if not entry:
            return None if not withTimestamp else (None, None)

        filtered = [q for q in entry.quotes if q.timestamp > timestamp]
        if not filtered:
            return None if not withTimestamp else (None, None)

        if not withTimestamp:
            return self._returnSingle(filtered[0], entry, currency)
        else:
            return self._returnSingle(filtered[0], entry, currency), filtered[0].timestamp
