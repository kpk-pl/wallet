from flask import render_template, request, json

from flaskr import db, header
from flaskr.session import Session
from flaskr.model import Asset
from flaskr.analyzers import Profits, Categories
from flaskr.analyzers.aggregate import aggregate
from flaskr.pricing import Context, Pricing

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


def wallet():
    session = Session(['label', 'debug'])
    headerData = header.HeaderData(showLabels = True)

    assets = list(db.get_db().assets.aggregate(_getPipeline(session.label())))
    aggregation = request.args.get('aggregation', default='')
    for aggrType in aggregation:
        assets = aggregate(assets, aggrType)

    assets = [Profits(asset)() for asset in assets]

    pricing = Pricing()
    pricingQuarterAgo = Pricing(Context(finalDate = datetime.now() - relativedelta(months=3)))

    for asset in assets:
        if session.isDebug():
            asset['_pricingData'] = {}

        currentPrice, quantity = pricing.priceAsset(asset, debug=asset['_pricingData'] if session.isDebug() else None)

        if currentPrice is not None:
            asset['_netValue'] = currentPrice

            quarterAgoPrice, quantityQuarterAgo = pricingQuarterAgo.priceAsset(asset)
            if quarterAgoPrice is not None and quantityQuarterAgo > 0:
                asset['_quarterValueChange'] = (currentPrice/quantity - quarterAgoPrice/quantityQuarterAgo) / (quarterAgoPrice/quantityQuarterAgo)
        else:
            asset['_netValue'] = None
            headerData.warnings.append(f"Could not determine current value of '{asset['name']}'")

    try:
        categoryAllocation = Categories()(assets)
    except RuntimeError as err:
        headerData.errors.append(str(err))
        categoryAllocation = None

    return render_template("wallet/wallet.html",
                           assets=assets,
                           allocation=json.dumps(categoryAllocation),
                           header = headerData.asDict())
