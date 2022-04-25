from flask import request, Response
from flaskr import db
from dataclasses import dataclass, asdict
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from flaskr.pricing import Context, HistoryPricing
from flaskr.analyzers import Profits
from flaskr.utils import jsonify
from flaskr.model import Asset
from decimal import Decimal


def _getPipelineForIdsHistorical(daysBack, label = None, ids = []):
    pipeline = []

    match = {}
    if ids:
        match['_id'] = { "$in": [ObjectId(id) for id in ids] }
    if label is not None:
        match['labels'] = label

    pipeline.append({ "$match" : match })
    pipeline.append({ "$addFields" : {
        "finalOperation": { "$last": "$operations" },
    }})

    pipeline.append({ "$match" : { '$or' : [
        { "finalOperation.finalQuantity": { "$ne": 0 } },
        { "finalOperation.date": {
          '$gte': datetime.now() - timedelta(days=daysBack)
        }}
    ]}})

    # TODO: Need to move this whole code to use strong types
    pipeline.append(
        { "$project" : {
            '_id': 1,
            'operations': 1,
            'currency': 1,
            'name': 1,
            'category': 1,
            'subcategory': { '$ifNull': [ "$subcategory", None ] },
            'pricing': 1,
            'type': 1,
            'institution': 1
        }}
    )

    return pipeline


@dataclass
class ResultAsset:
    id: str
    name: str
    category: str
    subcategory: str

    value: Decimal
    investedValue: Decimal
    quantity: Decimal

    def __init__(self, id, name, category, subcategory):
        self.id = str(id)
        self.name = name
        self.category = category
        self.subcategory = subcategory


@dataclass
class Result:
    t: list
    assets: list

    def __init__(self, timescale):
        self.t = timescale
        self.assets = []


def historicalValue():
    if request.method == 'GET':
        ids = list(set(request.args.getlist('id')))

        daysBack = None
        if 'daysBack' in request.args:
            daysBack = int(request.args.get('daysBack'))

        label = request.args.get('label')
        if not label:
            label = None

        investedValue = 'investedValue' in request.args

        now = datetime.now()
        pricingCtx = Context(finalDate = now, startDate = now - timedelta(daysBack))
        pricing = HistoryPricing(pricingCtx, features={'investedValue': investedValue})

        assets = list(db.get_db().assets.aggregate(_getPipelineForIdsHistorical(daysBack, ids=ids, label=label)))

        if investedValue:
            assets = [Profits(asset)() for asset in assets]

        result = Result(pricingCtx.timeScale)
        for asset in assets:
            strongAsset = Asset(**asset)
            dataAsset = ResultAsset(strongAsset.id, strongAsset.name, strongAsset.category, strongAsset.subcategory)

            # The second parameter to pricing should be profitsInfo, but that will be refactored to strong types later
            priced = pricing(strongAsset, asset)
            dataAsset.value = priced.value
            dataAsset.quantity = priced.quantity
            dataAsset.investedValue = priced.investedValue

            result.assets.append(dataAsset)

        return Response(jsonify(asdict(result)), mimetype="application/json")
