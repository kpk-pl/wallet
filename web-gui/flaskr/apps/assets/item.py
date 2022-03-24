from flask import render_template, request
from flaskr import db, header
from flaskr.analyzers import Profits, Operations
from flaskr.model import Asset
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
                "name": "$name",
                "data": "$quoteHistory",
            }}
        ],
        "as": "quoteInfo",
    }})
    pipeline.append({ "$project" : {
        "name": 1,
        "ticker": 1,
        "institution": 1,
        "category": 1,
        "subcategory": 1,
        "currency": 1,
        "type": 1,
        "pricing": 1,
        "link": 1,
        "labels": 1,
        "trashed": 1,
        "operations": { "$ifNull": [ '$operations', [] ] },
        "finalQuantity": { "$last": "$operations.finalQuantity" },
        "quoteHistory": { "$last": "$quoteInfo.data" },
        "pricingName": { "$last": "$quoteInfo.name" },
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

        weakAsset = assets[0]
        asset = Asset(**weakAsset)

        operations = Operations(asset.currency)(asset.operations)

        weakAsset['currency'] = weakAsset['currency']['name']
        weakAsset = Profits(weakAsset)()

        misc = dict(
            pricingName = weakAsset['pricingName'] if 'pricingName' in weakAsset else None
        )

        return render_template("assets/item.html", asset=weakAsset, operations=operations, misc=misc, header=header.data())
