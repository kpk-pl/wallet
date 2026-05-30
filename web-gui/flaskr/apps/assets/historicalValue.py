from flask import request, Response
from flaskr import db
from dataclasses import dataclass, asdict
from bson.objectid import ObjectId
from datetime import time, datetime, timedelta
from flaskr.pricing import Context, HistoryPricing
from flaskr.analyzers import Profits
from flaskr.utils import jsonify
from flaskr.model import Asset, AssetPricingQuotes
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


def _maxDaysBack(label = None, ids = [], default = 180):
    match = {
        "operations": { "$exists": True, "$not": { "$size": 0 } }
    }

    if ids:
        match['_id'] = { "$in": [ObjectId(id) for id in ids] }
    if label is not None:
        match['labels'] = label

    pipeline = [
        { "$match": match },
        { "$project": { "first": { "$min": "$operations.date" } } },
        { "$group": { "_id": None, "earliest": { "$min": "$first" } } },
    ]

    result = list(db.get_db().assets.aggregate(pipeline))
    if not result or not result[0].get('earliest'):
        return default

    return (datetime.now() - result[0]['earliest']).days + 1


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
    provision: List[Decimal]

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

        alignTimescale = None
        if 'alignTimescale' in request.args:
            alignTimescale = time.fromisoformat(request.args.get('alignTimescale'))

        label = request.args.get('label')
        if not label:
            label = None

        daysBack = 180
        if 'daysBack' in request.args:
            requestedDaysBack = request.args.get('daysBack')
            if requestedDaysBack == 'max':
                daysBack = _maxDaysBack(label=label, ids=ids, default=daysBack)
            else:
                daysBack = int(requestedDaysBack)

        investedValue = 'investedValue' in request.args

        now = datetime.now()
        pricingCtx = Context(finalDate = now,
                             startDate = now - timedelta(daysBack),
                             alignTimescale = alignTimescale)
        pricing = HistoryPricing(pricingCtx, features={'investedValue': investedValue, 'profit': investedValue})
        profits = Profits()

        rawAssets = list(db.get_db().assets.aggregate(_getPipelineForIdsHistorical(daysBack, ids=ids, label=label)))
        assets = [Asset(**rawAsset) for rawAsset in rawAssets]

        # Pre-load every quote referenced by the whole batch in a single DB round
        # trip. Without this, HistoryPricing.loadQuotes runs once per asset, which
        # over a wide window means N latency-bound queries against (a remote) Mongo.
        quoteIds = []
        for asset in assets:
            if isinstance(asset.pricing, AssetPricingQuotes):
                quoteIds.append(asset.pricing.quoteId)
            if asset.currency.quoteId is not None:
                quoteIds.append(asset.currency.quoteId)
        pricingCtx.loadQuotes(quoteIds)

        result = Result(pricingCtx.timeScale)
        for asset in assets:
            dataAsset = ResultAsset(asset.id, asset.name, asset.category, asset.subcategory)

            if investedValue:
                priced = pricing(asset, profitsInfo = profits(asset))
                dataAsset.investedValue = priced.investedValue
            else:
                priced = pricing(asset)

            dataAsset.value = priced.value
            dataAsset.quantity = priced.quantity
            dataAsset.provision = priced.provision
            dataAsset.profit = priced.profit

            result.assets.append(dataAsset)

        return Response(jsonify(asdict(result)), mimetype="application/json")
