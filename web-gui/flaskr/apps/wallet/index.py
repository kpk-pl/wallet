from flask import render_template, request, json, current_app

from flaskr import db, header
from flaskr.analyzers.profits import Profits
from flaskr.analyzers.categories import Categories
from flaskr.pricing import Pricing, PricingContext

from bson.objectid import ObjectId

from datetime import datetime, timedelta, timezone
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


def _getPipelineRecentlyClosed(label = None):
    pipeline = _getPipelineFilters(label)

    # When changing the history context, change also the html template for 'daysBack'
    pipeline.append({ "$match" : {
        "finalOperation.finalQuantity": 0,
        "finalOperation.date": {
          '$gte': datetime.now() - timedelta(days=60 + 1)
        }
    }})

    pipeline.append({ "$project" : { "_id": 1 }})

    return pipeline


def index():
    if request.method == 'GET':
        debug = bool(request.args.get('debug'))
        label = request.args.get('label')

        assets = list(db.get_db().assets.aggregate(_getPipeline(label)))
        assets = [Profits(asset)() for asset in assets]

        pricing = Pricing()
        pricingQuarterAgo = Pricing(PricingContext(finalDate = datetime.now() - relativedelta(months=3)))

        for asset in assets:
            if debug:
                asset['_pricingData'] = {}
            currentPrice, quantity = pricing.priceAsset(asset, debug=asset['_pricingData'] if debug else None)
            asset['_netValue'] = currentPrice

            quarterAgoPrice, quantityQuarterAgo = pricingQuarterAgo.priceAsset(asset)
            if quarterAgoPrice is not None and quantityQuarterAgo > 0:
                asset['_quarterValueChange'] = (currentPrice/quantity - quarterAgoPrice/quantityQuarterAgo) / (quarterAgoPrice/quantityQuarterAgo)

        categoryAnalyzer = Categories()
        categoryAllocation = categoryAnalyzer(assets)

        recentlyClosedIds = [e['_id'] for e in db.get_db().assets.aggregate(_getPipelineRecentlyClosed(label))]
        misc = {
            'showData': debug,
            'recentlyClosedIds': [e['_id'] for e in db.get_db().assets.aggregate(_getPipelineRecentlyClosed(label))],
        }

        return render_template("index.html",
                               assets=assets,
                               allocation=json.dumps(categoryAllocation),
                               header = header.data(),
                               misc=misc)
