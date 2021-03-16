from flask import request, json, Response, render_template
from flaskr import db
from flaskr.quotes import getQuote
from bson.objectid import ObjectId
from dateutil import parser


def quote():
    if request.method == 'GET':
        quoteUrl = request.args.get('url')
        response = getQuote(quoteUrl)
        return Response(json.dumps(response), mimetype="application/json")
    elif request.method == 'POST':
        query = {'_id': ObjectId(request.form['_id'])}
        update = {'$push': {'quoteHistory': {
            '$each': [{
                'timestamp': parser.parse(request.form['timestamp']),
                'quote': float(request.form['quote'])
            }],
            '$sort': {'timestamp': 1}
        }}}

        if request.form['assetType'] == 'assets':
            db.get_db().assets.update(query, update)
        elif request.form['assetType'] == 'currencies':
            db.get_db().currencies.update(query, update)
        return Response(), 204

def quote_add():
    if request.method == 'GET':
        assetId = request.args.get('asset')
        currencyId = request.args.get('currency')

        if assetId:
            assetDb = db.get_db().assets
            assetType = 'assets'
        elif currencyId:
            assetDb = db.get_db().currencies
            assetType = 'currencies'
        else:
            return Response(), 404

        pipeline = []
        pipeline.append({ "$match": {
            "_id": ObjectId(assetId if assetId else currencyId)
        }})
        pipeline.append({ "$addFields" : {
            "lastQuote": { "$last": "$quoteHistory" },
        }})

        assets = list(assetDb.aggregate(pipeline))
        if not assets:
            return Response(), 404

        return render_template("quote/add.html", asset=assets[0], assetType=assetType, date=request.args.get('date'), ref=request.args.get('ref'))
