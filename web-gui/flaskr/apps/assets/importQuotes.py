from flask import render_template, request
from flaskr import db
from bson.objectid import ObjectId


def _getPipelineForImportQuotes(assetId):
    pipeline = []
    pipeline.append({ "$match" : { "_id" : ObjectId(assetId) } })
    pipeline.append({ "$project": {
        '_id': 1,
        'name': 1,
        'ticker': 1,
        'quoteHistory': 1,
        'stooqSymbol': 1,
        'link': 1
    }})
    return pipeline


def asset_importQuotes():
    if request.method == 'GET':
        assetId = request.args.get('id')
        if not assetId:
            return ('', 400)

        assets = list(db.get_db().assets.aggregate(_getPipelineForImportQuotes(assetId)))
        if not assets:
            return ('', 404)

        return render_template("asset/import_quotes.html", asset=assets[0])
    elif request.method == 'POST':
        return ('', 204)
