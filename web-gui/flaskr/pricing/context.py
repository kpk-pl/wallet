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


    def __init__(self, finalDate = None, startDate = None):
        super(Context, self).__init__()
        self.finalDate = finalDate if finalDate is not None else datetime.now()
        self.startDate = startDate
        self.timeScale = _dayByDay(startDate, finalDate) if startDate is not None else []
        self.quotes = []

    def storedIds(self):
        return set(q.id for q in self.quotes)

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
            {'$project': {
                '_id': 1,
                'currencyPair': 1,
                'quotes': projection
            }}
        ]

        for item in db.get_db().quotes.aggregate(pipeline):
            if self.startDate:
                item['quotes'] = interp(item['quotes'], self.timeScale)

            self.quotes.append(self.StorageType(**item))

    def getFinalById(self, quoteId, currency=None):
        entry = next(x for x in self.quotes if x.id == quoteId)
        if not entry:
            return None

        result = entry.quotes[-1].quote
        if not entry.currencyPair:
            return result

        if currency == "GBP" and entry.currencyPair.destination == "GBX":
            result *= 100.0
        elif currency == "GBX" and entry.currencyPair.destination == "GBP":
            result /= 100.0

        return result

    def getHistoricalById(self, quoteId, currency=None):
        entry = next(x for x in self.quotes if x.id == quoteId)
        if not entry:
            return None

        result = [x.quote for x in entry.quotes]
        if not entry.currencyPair:
            return result

        if currency == "GBP" and entry.currencyPair.destination == "GBX":
            result = [q*100.0 for q in result]
        elif currency == "GBX" and entry.currencyPair.destination == "GBP":
            result = [q/100.0 for q in result]

        return result
