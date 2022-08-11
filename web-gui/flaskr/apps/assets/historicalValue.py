from flask import request, Response
from flaskr import db
from dataclasses import dataclass, asdict
from bson.objectid import ObjectId
from datetime import time, datetime, timedelta
from flaskr.pricing import Context, HistoryPricing
from flaskr.analyzers import Profits
from flaskr.utils import jsonify
from flaskr.model import Asset
from decimal import Decimal
from typing import List, Optional


def _getPipelineForIdsHistorical(daysBack, label = None, ids = []):
    pipeline = []

    match = {
        "operations": { "$exists": True, "$not": { "$size": 0 } }
    }

    if ids:
        match['_id'] = { "$in": [ObjectId(id) for id in ids] }
    if label is not None:
        match['labels'] = label

    pipeline.append({ "$match" : match })
    pipeline.append({ "$addFields" : {
        "finalOperation": { "$last": "$operations" },
        "subcategory": { '$ifNull': [ "$subcategory", None ] },
    }})

    # Only assets that are now active OR those that were sold in the time window
    pipeline.append({ "$match" : { '$or' : [
        { "finalOperation.finalQuantity": { "$ne": 0 } },
        { "finalOperation.date": {
          '$gte': datetime.now() - timedelta(days=daysBack)
        }}
    ]}})

    return pipeline


@dataclass
class ResultAsset:
    id: str
    name: str
    category: str
    subcategory: Optional[str]

    value: List[Decimal]
    quantity: List[Decimal]
    investedValue: Optional[List[Decimal]]
    profit: List[Decimal]

    def __init__(self, id, name, category, subcategory):
        self.id = str(id)
        self.name = name
        self.category = category
        self.subcategory = subcategory


@dataclass
class Result:
    t: List[datetime]
    assets: List[ResultAsset]

    def __init__(self, timescale):
        self.t = timescale
        self.assets = []


def historicalValue():
    if request.method == 'GET':
        ids = list(set(request.args.getlist('id')))

        daysBack = None
        if 'daysBack' in request.args:
            daysBack = int(request.args.get('daysBack'))

        alignTimescale = None
        if 'alignTimescale' in request.args:
            alignTimescale = time.fromisoformat(request.args.get('alignTimescale'))

        label = request.args.get('label')
        if not label:
            label = None

        investedValue = 'investedValue' in request.args

        now = datetime.now()
        pricingCtx = Context(finalDate = now,
                             startDate = now - timedelta(daysBack),
                             alignTimescale = alignTimescale)
        pricing = HistoryPricing(pricingCtx, features={'investedValue': investedValue, 'profit': investedValue})
        profits = Profits()

        assets = list(db.get_db().assets.aggregate(_getPipelineForIdsHistorical(daysBack, ids=ids, label=label)))

        result = Result(pricingCtx.timeScale)
        for rawAsset in assets:
            asset = Asset(**rawAsset)

            dataAsset = ResultAsset(asset.id, asset.name, asset.category, asset.subcategory)

            if investedValue:
                priced = pricing(asset, profitsInfo = profits(asset))
                dataAsset.investedValue = priced.investedValue
            else:
                priced = pricing(asset)

            dataAsset.value = priced.value
            dataAsset.quantity = priced.quantity
            dataAsset.profit = priced.profit

            result.assets.append(dataAsset)

        return Response(jsonify(asdict(result)), mimetype="application/json")
