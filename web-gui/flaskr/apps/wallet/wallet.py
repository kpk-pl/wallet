from flask import render_template, request

from flaskr import db, header
from flaskr.session import Session
from flaskr.model import Asset
from flaskr.analyzers import Profits, Categories
from flaskr.analyzers.aggregate import aggregate
from flaskr.pricing import Context, Pricing
from flaskr.utils import jsonify
from decimal import Decimal

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
    pipeline.append({ "$addFields" : {
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

    for rawAsset in assets:
        asset = Asset(**rawAsset)
        if session.isDebug():
            rawAsset['_pricingData'] = {}

        # TODO: Need to switch Profits analyzer to using Decimals and strong types
        rawAsset['_stillInvestedNetValue'] = Decimal(rawAsset['_stillInvestedNetValue'])

        currentPrice, quantity = pricing(asset, debug=rawAsset['_pricingData'] if session.isDebug() else None)

        if currentPrice is not None:
            rawAsset['_netValue'] = currentPrice

            quarterAgoPrice, quantityQuarterAgo = pricingQuarterAgo(asset)
            if quarterAgoPrice is not None and quantityQuarterAgo > 0:
                rawAsset['_quarterValueChange'] = (currentPrice/quantity - quarterAgoPrice/quantityQuarterAgo) / (quarterAgoPrice/quantityQuarterAgo)
        else:
            rawAsset['_netValue'] = None
            headerData.warnings.append(f"Could not determine current value of '{rawAsset['name']}'")

    try:
        categoryAllocation = Categories()(assets)
    except RuntimeError as err:
        headerData.errors.append(str(err))
        categoryAllocation = None

    return render_template("wallet/wallet.html",
                           assets=assets,
                           allocation=jsonify(categoryAllocation),
                           header = headerData.asDict())
