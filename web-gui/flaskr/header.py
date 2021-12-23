from dataclasses import dataclass, asdict
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
        'label': {'$addToSet': '$labels'}
    }})

    return pipeline


@dataclass
class HeaderLastQuoteUpdate:
    timestamp: datetime
    daysPast: int

    def __init__(self):
        self.timestamp = db.last_quote_update_time()
        self.daysPast = (datetime.now() - self.timestamp).days


@dataclass
class HeaderData:
    showLabels : bool
    allLabels : list[str]
    lastQuoteUpdate : HeaderLastQuoteUpdate

    def __init__(self, showLabels = False):
        self.showLabels = showLabels

        self.allLabels = next(db.get_db().assets.aggregate(_allLabelsPipeline()))['label']

        self.lastQuoteUpdate = HeaderLastQuoteUpdate()

    def asDict(self):
        return asdict(self)


def data(*args, **kwargs):
    return HeaderData(*args, **kwargs).asDict()
