from datetime import datetime, time, timedelta
from flaskr.pricing.interp import interp
from flaskr import db


def _dayByDay(start, finish):
    idx = datetime.combine(start.date(), time())
    oneDay = timedelta(days=1)
    result = []

    while idx <= finish:
        result.append(idx)
        idx += oneDay

    return result


class Context(object):
    def __init__(self, finalDate = None, startDate = None):
        super(Context, self).__init__()
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
        item['quotes'] = interp(item['quotes'], self.timeScale)
        self.quotes.append(item)

    def getFinalById(self, quoteId):
        quotesForId = [x['quotes'] for x in self.quotes if x['_id'] == quoteId]
        if not quotesForId or not quotesForId[-1]:
            return None

        return quotesForId[-1][0]['quote']

    def getHistoricalById(self, quoteId):
        quotes = next(x['quotes'] for x in self.quotes if x['_id'] == quoteId)
        return [x['quote'] for x in quotes]
