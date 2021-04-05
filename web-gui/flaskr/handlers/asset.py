from flask import render_template, request
from flaskr import db, quotes
from bson.objectid import ObjectId
from dateutil import parser
from flaskr.stooq import Stooq


def _getPipelineForAssetDetails(assetId):
    pipeline = []
    pipeline.append({ "$match" : { "_id" : ObjectId(assetId) } })
    pipeline.append({ "$addFields" : { "finalQuantity": { "$last": "$operations.finalQuantity" } }})
    return pipeline


def asset():
    if request.method == 'GET':
        assetId = request.args.get('id')
        if not assetId:
            return ('', 400)

        assets = list(db.get_db().assets.aggregate(_getPipelineForAssetDetails(assetId)))
        if not assets:
            return ('', 404)

        return render_template("asset/_.html", asset=assets[0])
    elif request.method == 'POST':
        data = {}

        allowedKeys = ['name', 'ticker', 'currency', 'link', 'type', 'category', 'subcategory', 'region', 'institution']
        for key in allowedKeys:
            if key in request.form.keys() and request.form[key]:
                data[key] = request.form[key]

        if data['link'].startswith("https://stooq.pl"):
            data['stooqSymbol'] = Stooq(data['link'])

        db.get_db().assets.insert(data)
        return ('', 204)


def asset_add():
    if request.method == 'GET':
        return render_template("asset/add.html")


# TODO: need to handle buying more of an asset that do not have
# URI and realtime tracking of quotes
# probably just calculate average between last quote/quantity
# and the ones that is being bought?
def asset_receipt():
    if request.method == 'GET':
        id = request.args.get('id')
        if not id:
            return ('', 400)

        pipeline = [
            { "$match" : { "_id" : ObjectId(id) } },
            {
                "$addFields" : {
                    "finalQuantity": { "$last": "$operations.finalQuantity" },
                }
            },
            { "$unset" : ["quoteHistory"] }
        ]

        assets = list(db.get_db().assets.aggregate(pipeline))
        if not assets:
            return ('', 404)

        asset = assets[0]
        if 'link' in asset:
            asset['lastQuote'] = quotes.getQuote(asset['link'])
        return render_template("asset/receipt.html", asset=asset)

    elif request.method == 'POST':
        operation = {
            'date': parser.parse(request.form['date']),
            'type': request.form['type'],
            'quantity': float(request.form['quantity']),
            'finalQuantity': float(request.form['finalQuantity']),
            'price': float(request.form['price'])
        }

        provision = float(request.form['provision'])
        if provision > 0:
            operation['provision'] = provision

        if 'currencyConversion' in request.form.keys():
            operation['currencyConversion'] = float(request.form['currencyConversion'])

        query = {'_id': ObjectId(request.form['_id'])}
        update = {'$push': {'operations': operation }}

        if request.form['type'] == 'BUY':
            asset = db.get_db().assets.find_one(query)
            if asset and 'quoteHistory' not in asset:
                update['$push']['quoteHistory'] = {
                    'timestamp': operation['date'],
                    'quote': operation['price'] / operation['quantity']
                }

        db.get_db().assets.update(query, update)
        return ('', 204)
