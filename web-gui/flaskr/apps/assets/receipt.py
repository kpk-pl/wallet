from flask import render_template, request, jsonify
from flaskr import db, header
from flaskr.session import Session
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


def receipt():
    if request.method == 'GET':
        session = Session(['debug'])

        id = request.args.get('id')
        if not id:
            return ({"error": "No id provided in request"}, 400)

        pipeline = [
            { "$match" : { "_id" : ObjectId(id) } },
            { "$project" : {
                '_id': 1,
                'name': 1,
                'pricing': 1,
                'type': 1,
                'ticker': 1,
                'institution': 1,
                'currency': 1,
                'labels': 1,
                'link': 1,
                'finalQuantity': { '$last': '$operations.finalQuantity' }
            }}
        ]

        assets = list(db.get_db().assets.aggregate(pipeline))
        if not assets:
            return ({"error": "Could not find asset"}, 404)

        asset = assets[0]

        if 'pricing' in asset and 'quoteId' in asset['pricing']:
            quote = list(db.get_db().quotes.aggregate([
                {'$match': {'_id': ObjectId(asset['pricing']['quoteId'])}},
                {'$project': {'lastQuote': {'$last': '$quoteHistory.quote'}}}
            ]))
            if quote:
                asset['lastQuote'] = quote[0]['lastQuote']

        if asset['currency']['name'] != 'PLN':
            quote = list(db.get_db().quotes.aggregate([
                {'$match': {'_id': ObjectId(asset['currency']['quoteId'])}},
                {'$project': {'lastQuote': {'$last': '$quoteHistory.quote'}}}
            ]))
            if quote:
                asset['lastCurrencyRate'] = quote[0]['lastQuote']

        return render_template("receipt.html", asset=asset, header=header.data())

    elif request.method == 'POST':
        operation = {
            'date': parser.parse(request.form['date']),
            'type': request.form['type'],
            'quantity': _parseNumeric(request.form['quantity']),
            'finalQuantity': _parseNumeric(request.form['finalQuantity'])
        }

        if 'price' in request.form.keys():
            operation['price'] = float(request.form['price'])
        else:
            operation['price'] = operation['quantity']  # for Deposit type, default unit price is 1

        if 'provision' in request.form.keys():
            provision = _parseNumeric(request.form['provision'])
            if provision:
                operation['provision'] = provision

        if 'currencyConversion' in request.form.keys():
            operation['currencyConversion'] = float(request.form['currencyConversion'])

        if 'code' in request.form.keys() and request.form['code']:
            operation['code'] = request.form['code']

        query = {'_id': ObjectId(request.form['_id'])}
        update = {'$push': {'operations': operation }}

        db.get_db().assets.update(query, update)
        return ('', 204)
