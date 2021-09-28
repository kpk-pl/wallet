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
    label : str
    allLabels : list
    lastQuoteUpdate : HeaderLastQuoteUpdate

    def __init__(self):
        self.label = request.args.get('label')
        if not self.label:
            self.label = None

        self.allLabels = next(db.get_db().assets.aggregate(_allLabelsPipeline()))['label']

        self.lastQuoteUpdate = HeaderLastQuoteUpdate()

    def asDict(self):
        return asdict(self)


def data(*args):
    return HeaderData(*args).asDict()
