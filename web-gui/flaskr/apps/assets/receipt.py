from flask import render_template, request, jsonify, current_app
from flaskr import db, header, typing
from flaskr.session import Session
from bson.objectid import ObjectId
import bson.errors
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
            'currency.name': {'$in': [asset['currency']['name'], typing.Currency.main]},
        }}
    ]))

    return render_template("assets/receipt.html", asset=asset, depositAccounts=depositAccounts, header=header.data())


class ReceiptError(RuntimeError):
    def __init__(self, code, msg):
        super(RuntimeError, self).__init__(msg)
        self.code = code
        self.message = msg

    def response(self):
        return dict(
            error = True,
            message = self.message,
            code = self.code
        )


def _required(param, errorCode):
    if param not in request.form:
        raise ReceiptError(errorCode, f"Missing required field {param}")
    return request.form[param]


def _makeOperation(asset):
    operation = {
        'date': parser.parse(_required("date", 100)),
        'type': _required("type", 101),
    }

    if operation['type'] != typing.Operation.Type.earning or asset['type'] == 'Deposit':
        operation['quantity'] = _parseNumeric(_required("quantity", 102))

    if asset['type'] == 'Deposit':
        if operation['type'] == typing.Operation.Type.receive:
            raise ReceiptError(10, "Deposit asset does not support RECEIVE")

    operation['finalQuantity'] = typing.Operation.adjustQuantity(operation['type'],
                                                                 asset['finalQuantity'],
                                                                 operation['quantity'] if 'quantity' in operation else None)

    if operation['finalQuantity'] < 0:
        raise ReceiptError(11, "Final quantity after operation cannot be less than zero")

    if asset['type'] == 'Deposit':
        operation['price'] = operation['quantity']  # for Deposit type, default unit price is 1
        if operation['type'] == typing.Operation.Type.earning:
            operation['finalQuantity'] += operation['quantity']
    else:
        operation['price'] = _parseNumeric(_required("price", 103))

    operation['finalQuantity'] = round(operation['finalQuantity'], typing.Currency.decimals)

    provisionSupportTypes = [typing.Operation.Type.buy, typing.Operation.Type.sell, typing.Operation.Type.earning]
    if 'provision' in request.form and operation['type'] in provisionSupportTypes:
        provision = _parseNumeric(request.form['provision'])
        if provision:
            operation['provision'] = provision

    if asset['currency']['name'] != typing.Currency.main:
        operation['currencyConversion'] = float(_required('currencyConversion', 104))

    if asset['coded']:
        operation['code'] = _required('code', 105)

    return operation


def _makeBillingOperation(asset, operation, session):
    if 'billingAsset' not in request.form or not request.form['billingAsset']:
        return None, None

    billingSupportTypes = [typing.Operation.Type.buy, typing.Operation.Type.sell, typing.Operation.Type.earning]
    if operation['type'] not in billingSupportTypes:
        raise ReceiptError(200, "Unsupported operation type for billing asset")

    if operation['type'] == typing.Operation.Type.earning and asset['type'] == 'Deposit':
        raise ReceiptError(201, "EARNING on Deposit does not support billing")

    try:
        query = {'_id': ObjectId(_required('billingAsset', 203))}
    except bson.errors.InvalidId:
        raise ReceiptError(202, "Invalid billingAsset id")

    billingAssets = list(db.get_db().assets.aggregate([
        {'$match': query},
        {'$project': {
            'type': 1,
            'currency': 1,
            # restore after a PR to mongomock is merged and new version released
            # 'finalQuantity': {'$ifNull': [{'$last': '$operations.finalQuantity'}, 0]}
            'finalQuantity': {'$ifNull': [{'$arrayElemAt': ['$operations.finalQuantity', -1]}, 0]}
        }}
    ], session=session))

    if not billingAssets:
        raise ReceiptError(203, "Unknown billing asset id")

    billingAsset = billingAssets[0]
    if billingAsset['type'] != 'Deposit':
        raise ReceiptError(204, "Billing asset must be a Deposit")

    billingOperation = {
        'date': operation['date'],
        'type': typing.Operation.Type.reverse(operation['type']),
        'quantity': operation['price']
    }

    if billingAsset['currency']['name'] != typing.Currency.main:
        assert 'currencyConversion' in operation  # checked already at code(104)
        billingOperation['currencyConversion'] = operation['currencyConversion']

    if asset['currency'] != billingAsset['currency']:
        assert 'currencyConversion' in operation  # checked already at code(104)
        if billingAsset['currency']['name'] != typing.Currency.main:
            raise ReceiptError(205, "Invalid billind asset currency")
        # if operation was in foreign currency then billing asset currency can only be the same or main
        # and here we know that the operation currency and billing asset currency are different

        billingOperation['quantity'] = billingOperation['quantity'] * operation['currencyConversion']

    if 'provision' in operation:
        billingOperation['quantity'] = typing.Operation.adjustQuantity(operation['type'],
                                                                       billingOperation['quantity'],
                                                                       operation['provision'])

    billingOperation['quantity'] = round(billingOperation['quantity'], typing.Currency.decimals)

    billingOperation['price'] = billingOperation['quantity']
    billingOperation['finalQuantity'] = typing.Operation.adjustQuantity(billingOperation['type'],
                                                                        billingAsset['finalQuantity'],
                                                                        billingOperation['quantity'])

    billingOperation['finalQuantity'] = round(billingOperation['finalQuantity'], typing.Currency.decimals)

    return query, billingOperation


def _receiptPost(session):
    if 'id' not in request.args.keys():
        return ({"error": True, "message": "No asset id provided", "code": 1}, 400)

    try:
        query = {'_id': ObjectId(request.args.get('id'))}
    except bson.errors.InvalidId:
        return ({"error": True, "message": "Invalid asset id", "code": 2}, 400)

    assets = list(db.get_db().assets.aggregate([
        {'$match': query},
        {'$project': {
            'type': 1,
            'currency': 1,
            'coded': { '$ifNull': ['$coded', False]},
            # use $last when it's supported in mongomock
            # 'finalQuantity': {'$ifNull': [{'$last': '$operations.finalQuantity'}, 0]}
            'finalQuantity': {'$ifNull': [{'$arrayElemAt': ['$operations.finalQuantity', -1]}, 0]}
        }}
    ], session=session))

    if not assets:
        return ({"error": True, "message": "Unknown asset id", "code": 3}, 400)

    asset = assets[0]

    try:
        operation = _makeOperation(asset)
    except ReceiptError as e:
        return (e.response(), 400)

    try:
        billingQuery, billingOperation = _makeBillingOperation(asset, operation, session)
    except ReceiptError as e:
        return (e.response(), 400)

    if billingQuery and not billingOperation:
        return ({"error": True, "message": "Could not resolve billing operation", "code": 4}, 400)

    db.get_db().assets.update_one(query, {'$push': {'operations': operation }}, session=session)
    if billingQuery:
        db.get_db().assets.update_one(billingQuery, {'$push': {'operations': billingOperation }}, session=session)

    return ({"ok": True}, 200)


def receipt():
    if request.method == 'GET':
        return _receiptGet()
    elif request.method == 'POST':
        if current_app.config['MONGO_SESSIONS']:
            with db.get_db().client.start_session() as session:
                return session.with_transaction(_receiptPost)
        else:
            return _receiptPost(None)
