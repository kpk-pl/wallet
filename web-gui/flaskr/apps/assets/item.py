from flask import render_template, request
from flaskr import db, header
from flaskr.analyzers import Profits
from flaskr.model import Asset, QuoteHistoryItem
from bson.objectid import ObjectId
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
                "data": "$quoteHistory",
            }}
        ],
        "as": "quoteInfo",
    }})
    return pipeline


@dataclass
class QuoteHistoryData:
    name: str
    data: List[QuoteHistoryItem]


def item():
    if request.method == 'GET':
        assetId = request.args.get('id')
        if not assetId:
            return ('', 400)

        assets = list(db.get_db().assets.aggregate(_getPipelineForAssetDetails(assetId)))
        if not assets:
            return ('', 404)

        asset = Asset(**assets[0])
        quoteHistory = QuoteHistoryData(**assets[0]['quoteInfo'][0]) if assets[0]['quoteInfo'] else None
        profitInfo = Profits()(asset)

        return render_template("assets/item.html",
                               asset=asset,
                               quoteHistory=quoteHistory,
                               profitInfo=profitInfo,
                               header=header.data())
