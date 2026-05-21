from flask import render_template, request

from flaskr import db, header
from flaskr.session import Session
from flaskr.model import Asset, AggregatedAsset, WalletAsset
from flaskr.analyzers import Profits, Categories, CategoryEntry
from flaskr.analyzers.aggregate import aggregate, AggregationType
from flaskr.pricing import Pricing
from flaskr.utils import jsonify
from decimal import Decimal
from dataclasses import dataclass
from typing import List, Optional


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
    asset: WalletAsset
    profits: Profits.Result
    debug: Optional[dict]
    netValue: Optional[Decimal]
    quantity: Optional[Decimal]
    isAggregated: bool = False


def wallet():
    session = Session(['label', 'debug'])
    headerData = header.HeaderData(showLabels = True)
    headerData.loadPriceFeedErrors()

    rawAssets = list(db.get_db().assets.aggregate(_getPipeline(session.label())))
    entries: List[WalletAsset] = [Asset(**a) for a in rawAssets]

    aggregation = request.args.get('aggregation', default='')
    for aggrType in aggregation:
        entries = aggregate(entries, AggregationType(aggrType))

    profitsAnalyzer = Profits()
    pricing = Pricing()

    assetData: List[WalletData] = []
    for entry in entries:
        debug = None
        if session.isDebug():
            debug = dict(pricing=dict(), quarterAgoPricing=dict(), profits=dict())

        netValue, quantity = pricing(entry, debug=debug['pricing'] if session.isDebug() else None)

        if netValue is None:
            headerData.warnings.append(f"Could not determine current value of '{entry.name}'")

        profits = profitsAnalyzer(entry, debug=debug['profits'] if session.isDebug() else None)
        assetData.append(WalletData(
            asset=entry,
            profits=profits,
            debug=debug,
            netValue=netValue,
            quantity=quantity,
            isAggregated=isinstance(entry, AggregatedAsset),
        ))

    try:
        categoryAllocation = Categories()([
            CategoryEntry(name=d.asset.name, category=d.asset.category,
                          subcategory=d.asset.subcategory, netValue=d.netValue)
            for d in assetData
        ])
    except RuntimeError as err:
        headerData.errors.append(str(err))
        categoryAllocation = None

    return render_template("wallet/wallet.html",
                           assetData=assetData,
                           allocation=jsonify(categoryAllocation),
                           header = headerData.asDict())
