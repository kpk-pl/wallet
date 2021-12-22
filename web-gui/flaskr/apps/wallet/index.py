from flask import render_template, make_response, request, json, current_app

from flaskr import db, header
from flaskr.session import Session
from flaskr.analyzers.profits import Profits
from flaskr.analyzers.categories import Categories
from flaskr.pricing import Context, Pricing

from bson.objectid import ObjectId

from datetime import datetime
from dateutil.relativedelta import relativedelta


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
        "ticker": 1,
        "institution": 1,
        "category": 1,
        "subcategory": 1,
        "currency": 1,
        "region": 1,
        "operations": 1,
        "pricing": 1,
        "finalQuantity": "$finalOperation.finalQuantity",
    }})

    return pipeline


def index():
    if request.method == 'GET':
        session = Session(['label', 'debug'])

        assets = list(db.get_db().assets.aggregate(_getPipeline(session.label())))
        assets = [Profits(asset)() for asset in assets]

        pricing = Pricing()
        pricingQuarterAgo = Pricing(Context(finalDate = datetime.now() - relativedelta(months=3)))

        for asset in assets:
            if session.isDebug():
                asset['_pricingData'] = {}
            currentPrice, quantity = pricing.priceAsset(asset, debug=asset['_pricingData'] if session.isDebug() else None)
            asset['_netValue'] = currentPrice

            quarterAgoPrice, quantityQuarterAgo = pricingQuarterAgo.priceAsset(asset)
            if quarterAgoPrice is not None and quantityQuarterAgo > 0:
                asset['_quarterValueChange'] = (currentPrice/quantity - quarterAgoPrice/quantityQuarterAgo) / (quarterAgoPrice/quantityQuarterAgo)

        categoryAnalyzer = Categories()
        categoryAllocation = categoryAnalyzer(assets)

        return render_template("wallet/index.html",
                               assets=assets,
                               allocation=json.dumps(categoryAllocation),
                               header = header.data(showLabels = True))
