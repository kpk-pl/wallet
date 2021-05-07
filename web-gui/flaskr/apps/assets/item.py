from flask import render_template, request, jsonify
from flaskr import db
from flaskr.analyzers.profits import Profits
from bson.objectid import ObjectId
from datetime import datetime
from flaskr.stooq import Stooq


def _getPipelineForAssetDetails(assetId):
    pipeline = []
    pipeline.append({ "$match" : { "_id" : ObjectId(assetId) } })
    pipeline.append({ "$project" : {
        "name": 1,
        "institution": 1,
        "category": 1,
        "subcategory": 1,
        "currency": '$currency.name',
        "type": 1,
        "pricing": 1,
        "link": 1,
        "labels": 1,
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

        if 'quoteId' in asset['pricing']:
            quoteHistory = list(db.get_db().quotes.aggregate(_getPipelineForAssetQuotes(asset['pricing']['quoteId'])))
            if quoteHistory:
                asset['quoteHistory'] = quoteHistory[0]['quoteHistory']

        lastQuoteUpdateTime = db.last_quote_update_time()
        misc = {
            'lastQuoteUpdate': {
                'timestamp': lastQuoteUpdateTime,
                'daysPast': (datetime.now() - lastQuoteUpdateTime).days
            }
        }

        return render_template("item.html", asset=asset, misc=misc)

    elif request.method == 'POST':
        data = {}

        allowedKeys = ['name', 'ticker', 'currency', 'link', 'type', 'category', 'subcategory', 'region', 'institution']
        for key in allowedKeys:
            if key in request.form.keys() and request.form[key]:
                data[key] = request.form[key]

        if data['link'].startswith("https://stooq.pl"):
            data['stooqSymbol'] = Stooq(url=data['link']).ticker

        addedId = db.get_db().assets.insert(data)
        return jsonify(id=str(addedId))
