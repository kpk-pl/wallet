from flask import render_template, request
from flaskr import db, header
from flaskr.analyzers import Profits
from flaskr.model import Asset, QuoteHistoryItem, AssetPricingParametrized
from flaskr.pricing.context import Context
from flaskr.pricing.pricing import HistoryPricing
from bson.objectid import ObjectId
from datetime import datetime
from typing import List
from dataclasses import dataclass


def _getPipelineForAssetDetails(assetId):
    pipeline = []
    pipeline.append({ "$match" : { "_id" : ObjectId(assetId) } })
    pipeline.append({ "$lookup" : {
        "from": "quotes",
        "let": {
            "pricingId": "$pricing.quoteId",
            "currencyId": "$currency.quoteId",
        },
        "pipeline": [
            { "$match": {
              "$or": [
                { "$expr": { "$eq": ["$_id", "$$pricingId"] }},
                { "$expr": { "$eq": ["$_id", "$$currencyId"] }}
              ]
            }},
            { "$project": {
                "_id": 0,
                "name": "$name",
                "data": {'$ifNull': ['$quoteHistory', []]},
            }}
        ],
        "as": "quoteInfo",
    }})
    return pipeline


@dataclass
class QuoteHistoryData:
    name: str
    data: List[QuoteHistoryItem]


def _computeParametrizedHistory(asset):
    if not asset.operations:
        return None

    ctx = Context(startDate=asset.operations[0].date, finalDate=datetime.now(), interpolate=True, keepOnlyFinalQuote=False)
    result = HistoryPricing(ctx)(asset)

    if result is None:
        return None

    data = [QuoteHistoryItem(timestamp=ts, quote=val)
            for ts, val in zip(result.timescale, result.value)]
    return QuoteHistoryData(name=asset.name, data=data)


def item():
    if request.method == 'GET':
        assetId = request.args.get('id')
        if not assetId:
            return ('', 400)

        assets = list(db.get_db().assets.aggregate(_getPipelineForAssetDetails(assetId)))
        if not assets:
            return ('', 404)

        asset = Asset(**assets[0])
        if assets[0]['quoteInfo']:
            quoteHistory = QuoteHistoryData(**assets[0]['quoteInfo'][0])
        elif isinstance(asset.pricing, AssetPricingParametrized):
            quoteHistory = _computeParametrizedHistory(asset)
        else:
            quoteHistory = None
        profitInfo = Profits()(asset)

        return render_template("assets/item.html",
                               asset=asset,
                               quoteHistory=quoteHistory,
                               profitInfo=profitInfo,
                               header=header.data())
