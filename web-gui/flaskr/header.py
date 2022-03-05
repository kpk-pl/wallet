from dataclasses import dataclass, field, asdict
from datetime import datetime
from flaskr import db
from flask import request


def _allLabelsPipeline():
    pipeline = []
    pipeline.append({'$unwind': {
        'path': '$labels',
        'preserveNullAndEmptyArrays': False
    }})
    pipeline.append({'$group': {
        '_id': None,
        'allLabels': {'$addToSet': '$labels'}
    }})

    return pipeline


def _lastQuoteUpdateTime():
    pipeline = [
        { '$project': {
            # mongomock error: 'lastQuote': { '$last': ['$quoteHistory.timestamp'] } }
          'lastQuote': { '$arrayElemAt': ['$quoteHistory.timestamp', -1] } }
        },
        { '$sort' : { 'lastQuote': -1 } },
        { '$limit' : 1 }
    ]

    result = list(db.get_db().quotes.aggregate(pipeline))
    if result and 'lastQuote' in result[0]:
        return result[0]['lastQuote']

    return None


@dataclass
class HeaderLastQuoteUpdate:
    timestamp: datetime
    daysPast: int

    @classmethod
    def create(cls):
        lastUpdateTime = _lastQuoteUpdateTime()
        if not lastUpdateTime:
            return None

        return cls(timestamp=lastUpdateTime, daysPast=(datetime.now() - lastUpdateTime).days)


@dataclass
class HeaderData:
    showLabels : bool
    allLabels : list[str]
    lastQuoteUpdate : HeaderLastQuoteUpdate

    warnings : list[str] = field(default_factory=list)
    errors : list[str] = field(default_factory=list)

    def __init__(self, showLabels = False):
        self.showLabels = showLabels

        labelsResult = list(db.get_db().assets.aggregate(_allLabelsPipeline()))
        self.allLabels = labelsResult[0]['allLabels'] if labelsResult else []

        self.lastQuoteUpdate = HeaderLastQuoteUpdate.create()

        self.warnings = []
        self.errors = []

    def asDict(self):
        return asdict(self)


def data(*args, **kwargs):
    return HeaderData(*args, **kwargs).asDict()
