from flask import render_template, request

from flaskr import db, header
from flaskr.session import Session
from flaskr.model import Asset
from flaskr.analyzers import StrongProfits, Categories
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

    profits = StrongProfits()
    pricing = Pricing()
    pricingQuarterAgo = Pricing(Context(finalDate = datetime.now() - relativedelta(months=3)))

    assetData = []
    for rawAsset in assets:
        data = dict()
        assetData.append(data)

        asset = Asset(**rawAsset)
        data['asset'] = asset

        if session.isDebug():
            data['debug'] = dict(pricing=dict(), quarterAgoPricing=dict(), profits=dict())

        netValue, quantity = pricing(asset, debug=data['debug']['pricing'] if session.isDebug() else None)
        data['netValue'] = netValue
        data['quantity'] = quantity

        if netValue is not None:
            quarterAgoValue, quarterAgoQuantity = pricingQuarterAgo(asset, debug=data['debug']['quarterAgoPricing'] if session.isDebug() else None)
            if quarterAgoValue is not None and quarterAgoQuantity > 0:
                data['quarterValueChange'] = (netValue/quantity - quarterAgoValue/quarterAgoQuantity) / (quarterAgoValue/quarterAgoQuantity)
        else:
            headerData.warnings.append(f"Could not determine current value of '{asset.name}'")

        data['profits'] = profits(asset, debug=data['debug']['profits'] if session.isDebug() else None)

    for i in range(len(assets)):
        assets[i]['_netValue'] = assetData[i]['netValue']
    try:
        categoryAllocation = Categories()(assets)
    except RuntimeError as err:
        headerData.errors.append(str(err))
        categoryAllocation = None

    return render_template("wallet/wallet.html",
                           assetData=assetData,
                           allocation=jsonify(categoryAllocation),
                           header = headerData.asDict())
