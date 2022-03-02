from flask import render_template, request
from flaskr import db, header
from flaskr.analyzers import Profits, Operations
from bson.objectid import ObjectId
from datetime import datetime


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
                "data": "$quoteHistory",
            }}
        ],
        "as": "quoteHistory",
    }})
    pipeline.append({ "$project" : {
        "name": 1,
        "ticker": 1,
        "institution": 1,
        "category": 1,
        "subcategory": 1,
        "currency": '$currency.name',
        "type": 1,
        "pricing": 1,
        "link": 1,
        "labels": 1,
        "trashed": 1,
        "operations": { "$ifNull": [ '$operations', [] ] },
        "finalQuantity": { "$last": "$operations.finalQuantity" },
        "quoteHistory": { "$last": "$quoteHistory.data" },
    }})
    return pipeline


def item():
    if request.method == 'GET':
        assetId = request.args.get('id')
        if not assetId:
            return ('', 400)

        assets = list(db.get_db().assets.aggregate(_getPipelineForAssetDetails(assetId)))
        if not assets:
            return ('', 404)

        asset = assets[0]
        operations = Operations(asset['currency'])(asset['operations'])
        asset = Profits(asset)()

        return render_template("assets/item.html", asset=asset, operations=operations, header=header.data())
