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
            'codes': 1,
            'finalQuantity': { '$ifNull': [{ '$last': '$operations.finalQuantity' }, 0] }
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

    if asset['currency']['name'] != typing.Currency.main:
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

    return render_template("assets/receipt.html", asset=asset, depositAccounts=depositAccounts, header=header.data())


def _required(param):
    if param not in request.form:
        raise Exception(f"Missing required field {param}")
    return request.form[param]


def _makeOperation(asset):
    operation = {
        'date': parser.parse(_required("date")),
        'type': _required("type"),
    }

    if operation['type'] != typing.Operation.Type.earning or asset['type'] == 'Deposit':
        operation['quantity'] = _parseNumeric(_required("quantity"))

    if asset['type'] == 'Deposit':
        if operation['type'] == typing.Operation.Type.receive:
            raise Exception("Deposit asset does not support RECEIVE")

    operation['finalQuantity'] = typing.Operation.adjustQuantity(operation['type'],
                                                                 asset['finalQuantity'],
                                                                 operation['quantity'] if 'quantity' in operation else None)

    if asset['type'] == 'Deposit':
        operation['price'] = operation['quantity']  # for Deposit type, default unit price is 1
        operation['finalQuantity'] += operation['quantity']
    else:
        operation['price'] = _parseNumeric(_required("price"))

    provisionSupportTypes = [typing.Operation.Type.buy, typing.Operation.Type.sell, typing.Operation.Type.earning]
    if 'provision' in request.form and operation['type'] in provisionSupportTypes:
        provision = _parseNumeric(request.form['provision'])
        if provision:
            operation['provision'] = provision

    if asset['currency']['name'] != typing.Currency.main:
        operation['currencyConversion'] = float(_required('currencyConversion'))

    if asset['coded']:
        operation['code'] = _required('code')

    return operation


def _makeBillingOperation(asset, operation, session):
    if 'billingAsset' not in request.form or not request.form['billingAsset']:
        return None, None

    billingSupportTypes = [typing.Operation.Type.buy, typing.Operation.Type.sell, typing.Operation.Type.earning]
    if operation['type'] not in billingSupportTypes:
        return None, None

    if operation['type'] == typing.Operation.Type.earning and asset['type'] == 'Deposit':
        return None, None

    query = {'_id': ObjectId(_required('billingAsset'))}

    billingAssets = list(db.get_db().assets.aggregate([
        {'$match': query},
        {'$project': {
            'currency': 1,
            'finalQuantity': {'$ifNull': [{'$last': '$operations.finalQuantity'}, 0]}
        }}
    ], session=session))

    if not billingAssets:
        return query, None

    billingAsset = billingAssets[0]

    billingOperation = {
        'date': operation['date'],
        'type': typing.Operation.Type.reverse(operation['type']),
        'quantity': operation['price']
    }

    if billingAsset['currency']['name'] != typing.Currency.main:
        assert 'currencyConversion' in operation
        billingOperation['currencyConversion'] = operation['currencyConversion']

    if asset['currency'] != billingAsset['currency']:
        assert 'currencyConversion' in operation
        assert billingAsset['currency']['name'] == typing.Currency.main
        # if operation was in foreign currency then billing asset currency can only be the same or main
        # and here we know that the operation currency and billing asset currency are different

        billingOperation['quantity'] = round(billingOperation['quantity'] * operation['currencyConversion'],
                                             typing.Currency.decimals)

    if 'provision' in operation:
        billingOperation['quantity'] -= operation['provision']

    billingOperation['price'] = billingOperation['quantity']
    billingOperation['finalQuantity'] = typing.Operation.adjustQuantity(billingOperation['type'],
                                                                        billingAsset['finalQuantity'],
                                                                        billingOperation['quantity'])

    return query, billingOperation


def _receiptPost(session):
    query = {'_id': ObjectId(request.form['_id'])}

    assets = list(db.get_db().assets.aggregate([
        {'$match': query},
        {'$project': {
            'type': 1,
            'currency': 1,
            'coded': { '$ifNull': ['$coded', False]},
            'finalQuantity': {'$ifNull': [{'$last': '$operations.finalQuantity'}, 0]}
        }}
    ], session=session))

    if not assets:
        return ({"error": "Unknown asset id"}, 400)

    asset = assets[0]

    try:
        operation = _makeOperation(asset)
    except Exception as e:
        return ({"error": str(e)}, 400)

    billingQuery, billingOperation = _makeBillingOperation(asset, operation, session)

    if billingQuery and not billingOperation:
        return ({"error": "Could not resolve billing operation"}, 400)

    db.get_db().assets.update_one(query, {'$push': {'operations': operation }}, session=session)
    if billingQuery:
        db.get_db().assets.update_one(billingQuery, {'$push': {'operations': billingOperation }}, session=session)

    return ({"ok": True}, 200)


def receipt():
    if request.method == 'GET':
        return _receiptGet()
    elif request.method == 'POST':
        with db.get_db().client.start_session() as session:
            return session.with_transaction(_receiptPost)
