from datetime import datetime, time, timedelta
from dataclasses import dataclass, field
from flaskr import db
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
    @dataclass
    class StorageType:
        _id: ObjectId
        quotes: list[tuple[datetime, float]] = field(default_factory=list)

        def __init__(self, desc):
            self._id = desc['_id']
            self.quotes = list(map(lambda q: (q['timestamp'], q['quote']), desc['quotes']))


    def __init__(self, finalDate = None, startDate = None):
        super(Context, self).__init__()
        self.finalDate = finalDate if finalDate is not None else datetime.now()
        self.startDate = startDate
        self.timeScale = _dayByDay(startDate, finalDate) if startDate is not None else []
        self.quotes = []

    def storedIds(self):
        return set(q._id for q in self.quotes)

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

        for item in db.get_db().quotes.aggregate(pipeline):
            if self.startDate:
                item['quotes'] = interp(item['quotes'], self.timeScale)

            self.quotes.append(Context.StorageType(item))

    def getFinalById(self, quoteId):
        quotesForId = next(x.quotes for x in self.quotes if x._id == quoteId)
        if not quotesForId:
            return None

        return quotesForId[-1][1]

    def getHistoricalById(self, quoteId):
        quotes = next(x.quotes for x in self.quotes if x._id == quoteId)
        return [x[1] for x in quotes]
