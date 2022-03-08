from flask import render_template, request, json, Response

from datetime import datetime
from flaskr import db, header
from flaskr.session import Session
from flaskr.pricing import Pricing
from flaskr.analyzers.categories import Categories


def _getPipelineFilters(label = None):
    pipeline = []

    match = {
        "operations": { "$exists": True, "$not": { "$size": 0 } }
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


def _lastStrategyPipeline(label = None):
    return [
        {'$match': {'label': label}},
        {'$sort': {'creationDate': -1}},
        {'$limit': 1},
        {'$project': {
            '_id': 0
        }}
    ]


def _response(shouldAllocate=False, label=None):
    response = {}

    strategy = list(db.get_db().strategy.aggregate(_lastStrategyPipeline(label)))
    if strategy:
        response['strategy'] = strategy[0]

    if shouldAllocate:
        response['label'] = label

        pricing = Pricing()
        assets = list(db.get_db().assets.aggregate(_getPipeline(label)))
        for asset in assets:
            asset['_netValue'], _ = pricing.priceAsset(asset)

        try:
            response['allocation'] = Categories()(assets)
        except RuntimeError as e:
            return None

    return response


def strategy():
    if request.method == 'GET':
        session = Session(['label'])
        return render_template("wallet/strategy.html", header=header.data(showLabels = True))

    elif request.method == 'POST':
        label = request.args.get('label')
        if not label:
            label = None

        data = json.loads(request.data.decode('utf-8'))

        for entry in data:
            entry['categories'] = [v['name'] if v['percentage'] == 100 else v for v in entry['categories']]

        db.get_db().strategy.insert(dict(
            creationDate = datetime.now(),
            assetTypes = data,
            label = label,
        ))

        return '', 201


def strategy_json():
    if request.method == 'GET':
        shouldAllocate = request.args.get('allocation') == 'true'
        label = request.args.get('label')
        if not label:
            label = None

        response = _response(shouldAllocate, label)
        if response is not None:
            return Response(json.dumps(response), mimetype="application/json")
        else:
            return '', 500
