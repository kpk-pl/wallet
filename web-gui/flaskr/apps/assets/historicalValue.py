from flask import request, Response, json
from flaskr import db
from dataclasses import dataclass, asdict
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from flaskr.pricing import PricingContext, Pricing


def _getPipelineForIdsHistorical(daysBack, label = None, ids = []):
    pipeline = []

    match = {'trashed': { '$ne': True }}
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

    pipeline.append(
        { "$project" : {
            '_id': 1,
            'operations': 1,
            'currency': 1,
            'name': 1,
            'category': 1,
            'subcategory': { '$ifNull': [ "$subcategory", None ] },
            'pricing': 1
        }}
    )

    return pipeline


@dataclass
class ResultAsset:
    name: str
    category: str
    subcategory: str

    value: list

    def __init__(self, name, category, subcategory):
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

        label = None
        if 'label' in request.args:
            label = request.args.get('label')

        now = datetime.now()
        pricingCtx = PricingContext(finalDate = now, startDate = now - timedelta(daysBack))
        pricing = Pricing(pricingCtx)

        assets = list(db.get_db().assets.aggregate(_getPipelineForIdsHistorical(daysBack, ids=ids, label=label)))

        result = Result(pricingCtx.timeScale)
        for asset in assets:
            dataAsset = ResultAsset(asset['name'], asset['category'], asset['subcategory'])

            priced = pricing.priceAssetHistory(asset)
            dataAsset.value = priced['y']

            result.assets.append(dataAsset)

        return Response(json.dumps(asdict(result)), mimetype="application/json")
