from flask import render_template, request

from flaskr import db, header
from flaskr.session import Session
from flaskr.model import Asset
from flaskr.analyzers import Profits, Categories
from flaskr.analyzers.aggregate import aggregate
from flaskr.pricing import Context, Pricing
from flaskr.utils import jsonify
from decimal import Decimal
from dataclasses import dataclass
from typing import Optional


def _getPipelineFilters(label = None):
    pipeline = []

    match = {
        "operations": { "$exists": True, "$not": { "$size": 0 } }
    }

    if label is not None:
        match['labels'] = label

    pipeline.append({ "$match" : match })
    pipeline.append({ "$addFields" : {
        "finalQuantity": { "$last": "$operations.finalQuantity" },
    }})

    return pipeline


def _getPipeline(label = None):
    pipeline = _getPipelineFilters(label)
    pipeline.append({ "$match" : {
        'trashed': { '$ne': True },
        "finalQuantity": { "$ne": 0 }
    }})

    return pipeline


@dataclass
class WalletData:
    asset: Asset
    profits: Profits.Result
    debug: Optional[dict]
    netValue: Optional[Decimal]
    quantity: Optional[Decimal]


def wallet():
    session = Session(['label', 'debug'])
    headerData = header.HeaderData(showLabels = True)

    assets = list(db.get_db().assets.aggregate(_getPipeline(session.label())))
    aggregation = request.args.get('aggregation', default='')
    for aggrType in aggregation:
        assets = aggregate(assets, aggrType)

    profitsAnalyzer = Profits()
    pricing = Pricing()

    assetData = []
    for rawAsset in assets:
        asset = Asset(**rawAsset)
        debug = None

        if session.isDebug():
            debug = dict(pricing=dict(), quarterAgoPricing=dict(), profits=dict())

        netValue, quantity = pricing(asset, debug=debug['pricing'] if session.isDebug() else None)

        if netValue is None:
            headerData.warnings.append(f"Could not determine current value of '{asset.name}'")

        profits = profitsAnalyzer(asset, debug=debug['profits'] if session.isDebug() else None)
        assetData.append(WalletData(asset, profits, debug, netValue, quantity))

    for asset, data in zip(assets, assetData):
        asset['_netValue'] = data.netValue

    try:
        categoryAllocation = Categories()(assets)
    except RuntimeError as err:
        headerData.errors.append(str(err))
        categoryAllocation = None

    return render_template("wallet/wallet.html",
                           assetData=assetData,
                           allocation=jsonify(categoryAllocation),
                           header = headerData.asDict())
