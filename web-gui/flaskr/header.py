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
        'allLabels': {'$addToSet': '$labels'}
    }})

    return pipeline


@dataclass
class HeaderLastQuoteUpdate:
    timestamp: datetime
    daysPast: int

    @classmethod
    def create(cls):
        lastUpdateTime = db.last_quote_update_time()
        if not lastUpdateTime:
            return None

        return cls(timestamp=lastUpdateTime, daysPast=(datetime.now() - lastUpdateTime).days)


@dataclass
class HeaderData:
    showLabels : bool
    allLabels : list[str]
    lastQuoteUpdate : HeaderLastQuoteUpdate

    def __init__(self, showLabels = False):
        self.showLabels = showLabels

        labelsResult = list(db.get_db().assets.aggregate(_allLabelsPipeline()))
        self.allLabels = labelsResult[0]['allLabels'] if labelsResult else []

        self.lastQuoteUpdate = HeaderLastQuoteUpdate.create()

    def asDict(self):
        return asdict(self)


def data(*args, **kwargs):
    return HeaderData(*args, **kwargs).asDict()
