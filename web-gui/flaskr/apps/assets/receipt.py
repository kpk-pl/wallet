from flask import render_template, request, jsonify
from flaskr import db, quotes
from bson.objectid import ObjectId
from dateutil import parser


def _parseNumeric(value):
    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        pass

    return None

# TODO: need to handle buying more of an asset that do not have
# URI and realtime tracking of quotes
# probably just calculate average between last quote/quantity
# and the ones that is being bought?
def receipt():
    if request.method == 'GET':
        id = request.args.get('id')
        if not id:
            return ('', 400)

        pipeline = [
            { "$match" : { "_id" : ObjectId(id) } },
            { "$project" : {
                '_id': 1,
                'name': 1,
                'ticker': 1,
                'institution': 1,
                'currency': 1,
                'finalQuantity': { '$last': '$operations.finalQuantity' },
                'lastQuote': { '$last': '$quoteHistory' }
            }}
        ]

        assets = list(db.get_db().assets.aggregate(pipeline))
        if not assets:
            return ('', 404)

        asset = assets[0]
        if 'link' in asset:
            asset['lastQuote'] = quotes.getQuote(asset['link'])
        return render_template("receipt.html", asset=asset)

    elif request.method == 'POST':
        operation = {
            'date': parser.parse(request.form['date']),
            'type': request.form['type'],
            'quantity': _parseNumeric(request.form['quantity']),
            'finalQuantity': _parseNumeric(request.form['finalQuantity']),
            'price': float(request.form['price'])
        }

        provision = request.form['provision']
        if provision:
            provision = float(provision)
            if provision > 0:
                operation['provision'] = provision

        if 'currencyConversion' in request.form.keys():
            operation['currencyConversion'] = float(request.form['currencyConversion'])

        if 'code' in request.form.keys() and request.form['code']:
            operation['code'] = request.form['code']

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
