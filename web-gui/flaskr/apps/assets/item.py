from flask import render_template, request
from flaskr import db, header
from flaskr.analyzers.profits import Profits
from bson.objectid import ObjectId
from datetime import datetime


def _getPipelineForAssetDetails(assetId):
    pipeline = []
    pipeline.append({ "$match" : { "_id" : ObjectId(assetId) } })
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
        "finalQuantity": { "$last": "$operations.finalQuantity" }
    }})
    return pipeline


def _getPipelineForAssetQuotes(quoteId):
    pipeline = []
    pipeline.append({'$match' : { '_id' : quoteId }})
    pipeline.append({'$project' : { 'quoteHistory' : 1 }})
    return pipeline


def item():
    if request.method == 'GET':
        assetId = request.args.get('id')
        if not assetId:
            return ('', 400)

        assets = list(db.get_db().assets.aggregate(_getPipelineForAssetDetails(assetId)))
        if not assets:
            return ('', 404)

        asset = Profits(assets[0])()

        if 'pricing' in asset and 'quoteId' in asset['pricing']:
            quoteHistory = list(db.get_db().quotes.aggregate(_getPipelineForAssetQuotes(asset['pricing']['quoteId'])))
            if quoteHistory:
                asset['quoteHistory'] = quoteHistory[0]['quoteHistory']

        return render_template("item.html", asset=asset, header=header.data())
