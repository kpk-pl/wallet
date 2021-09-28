from flask import render_template, request, json, Response

from flaskr import db, header
from flaskr.pricing import Pricing
from flaskr.analyzers.categories import Categories


def _getPipelineFilters(label = None):
    pipeline = []

    match = {
        "operations": { "$exists": True }
    }

    if label is not None:
        match['labels'] = label

    pipeline.append({ "$match" : match })
    pipeline.append({ "$addFields" : {
        "finalOperation": { "$last": "$operations" },
    }})

    return pipeline


def _getPipeline(label = None):
    pipeline = _getPipelineFilters(label)
    pipeline.append({ "$match" : {
        'trashed': { '$ne': True },
        "finalOperation.finalQuantity": { "$ne": 0 }
    }})
    pipeline.append({ "$project" : {
        "_id": 1,
        "name": 1,
        "category": 1,
        "subcategory": 1,
        "currency": 1,
        "operations": 1,
        "pricing": 1,
        "finalQuantity": "$finalOperation.finalQuantity",
    }})

    return pipeline


def _lastStrategyPipeline():
    return [
        {'$sort': {'creationDate': -1}},
        {'$limit': 1},
        {'$project': {'_id': 0}}
    ]


def _response(shouldAllocate=False, label=None):
    response = {}

    strategy = next(db.get_db().strategy.aggregate(_lastStrategyPipeline()))
    response['strategy'] = strategy

    if shouldAllocate:
        response['label'] = label

        pricing = Pricing()
        assets = list(db.get_db().assets.aggregate(_getPipeline(label)))
        for asset in assets:
            asset['_netValue'], _ = pricing.priceAsset(asset)

        categoryAnalyzer = Categories()
        response['allocation'] = categoryAnalyzer(assets)

    return response


def strategy():
    if request.method == 'GET':
        return render_template("strategy.html", header=header.data())


def strategy_json():
    if request.method == 'GET':
        shouldAllocate = request.args.get('allocation') == 'true'
        label = request.args.get('label')
        if not label:
            label = None

        response = _response(shouldAllocate, label)
        return Response(json.dumps(response), mimetype="application/json")
