from flask import render_template, request, jsonify
from flaskr import db, header, typing
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


def _receiptGet():
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
        if quote and 'lastQuote' in quote[0]:
            asset['lastQuote'] = quote[0]['lastQuote']

    if asset['currency']['name'] != 'PLN':
        quote = list(db.get_db().quotes.aggregate([
            {'$match': {'_id': ObjectId(asset['currency']['quoteId'])}},
            {'$project': {'lastQuote': {'$last': '$quoteHistory.quote'}}}
        ]))
        if quote:
            asset['lastCurrencyRate'] = quote[0]['lastQuote']

    depositAccounts = list(db.get_db().assets.aggregate([
        {'$match': {
            'trashed': {'$ne': True},
            'type': 'Deposit',
            'category': 'Cash',
            '_id': {'$ne': asset['_id']},
            'currency.name': asset['currency']['name']
        }}
    ]))

    return render_template("receipt.html", asset=asset, depositAccounts=depositAccounts, header=header.data())


def _makeOperation(asset):
    operation = {
        'date': parser.parse(request.form['date']),
        'type': request.form['type'],
        'quantity': _parseNumeric(request.form['quantity'])
    }

    operation['finalQuantity'] = typing.Operation.adjustQuantity(operation['type'],
                                                                 asset['finalQuantity'],
                                                                 operation['quantity'])

    if 'price' in request.form:
        operation['price'] = float(request.form['price'])
    else:
        operation['price'] = operation['quantity']  # for Deposit type, default unit price is 1

    if 'provision' in request.form:
        provision = _parseNumeric(request.form['provision'])
        if provision:
            operation['provision'] = provision

    if 'currencyConversion' in request.form:
        operation['currencyConversion'] = float(request.form['currencyConversion'])

    if 'code' in request.form and request.form['code']:
        operation['code'] = request.form['code']

    return operation


def _makeBillingOperation(asset, operation):
    if 'billingAsset' not in request.form or not request.form['billingAsset']:
        return None, None

    query = {'_id': ObjectId(request.form['billingAsset'])}

    billingAssets = list(db.get_db().assets.aggregate([
        {'$match': query},
        {'$project': {
            'currency': 1,
            'finalQuantity': {'$ifNull': [{'$last': '$operations.finalQuantity'}, 0]}
        }}
    ]))

    if not billingAssets:
        return query, None

    billingAsset = billingAssets[0]

    billingOperation = {
        'date': operation['date'],
        'type': typing.Operation.Type.reverse(operation['type']),
        'quantity': operation['price']
    }

    if billingAsset['currency'] != typing.Currency.main:
        assert 'currencyConversion' in operation
        billingOperation['currencyConversion'] = operation['currencyConversion']

    if asset['currency'] != billingAsset['currency']:
        assert 'currencyConversion' in operation
        assert billingAsset['currency']['name'] == typing.Currency.main
        # if operation was in foreign currency then billing asset currency can only be the same or main
        # and here we know that the operation currency and billing asset currency are different

        billingOperation['quantity'] = round(billingOperation['quantity'] * operation['currencyConversion'],
                                             typing.Currency.decimals)

    billingOperation['price'] = billingOperation['quantity']
    billingOperation['finalQuantity'] = typing.Operation.adjustQuantity(billingOperation['type'],
                                                                        billingAsset['finalQuantity'],
                                                                        billingOperation['quantity'])

    return query, billingOperation


def _receiptPost():
    query = {'_id': ObjectId(request.form['_id'])}

    assets = list(db.get_db().assets.aggregate([
        {'$match': query},
        {'$project': {
            'currency': 1,
            'finalQuantity': {'$ifNull': [{'$last': '$operations.finalQuantity'}, 0]}
        }}
    ]))

    if not assets:
        return ({"error": "Unknown asset id"}, 400)

    asset = assets[0]

    operation = _makeOperation(asset)
    billingQuery, billingOperation = _makeBillingOperation(asset, operation)

    if billingQuery and not billingOperation:
        return ({"error": "Could not resolve billing operation"}, 400)

    db.get_db().assets.update(query, {'$push': {'operations': operation }})
    if billingQuery:
        db.get_db().assets.update(billingQuery, {'$push': {'operations': billingOperation }})

    return ('', 204)


def receipt():
    if request.method == 'GET':
        return _receiptGet()
    elif request.method == 'POST':
        return _receiptPost()
