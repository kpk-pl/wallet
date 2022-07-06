from flask import render_template, request
from flaskr import db, header
from flaskr.analyzers import Profits, Operations
from flaskr.model import Asset, QuoteHistoryItem
from bson.objectid import ObjectId
from datetime import datetime
from typing import List
from dataclasses import dataclass


def _getPipelineForAssetDetails(assetId):
    pipeline = []
    pipeline.append({ "$match" : { "_id" : ObjectId(assetId) } })
    pipeline.append({ "$lookup" : {
        "from": "quotes",
        "let": { "pricingId" : "$pricing.quoteId" },
        "pipeline": [
            { "$match" : {
                "$expr": { "$eq": ["$_id", "$$pricingId"] }
            }},
            { "$project" : {
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
        operations = Operations(asset.currency)(asset.operations)
        profitInfo = Profits()(asset)

        return render_template("assets/item.html",
                               asset=asset,
                               quoteHistory=quoteHistory,
                               profitInfo=profitInfo,
                               operations=operations,
                               header=header.data())
