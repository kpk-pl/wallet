from flask import render_template, request, current_app
from flaskr import db, header, typing
from flaskr.session import Session
from bson.objectid import ObjectId
from bson.decimal128 import Decimal128
import bson.errors
from datetime import datetime
from dateutil import parser
from flaskr.model import Asset, AssetType, AssetPricingQuotes
from decimal import Decimal


def _parseNumeric(value):
    try:
        return int(value)
    except ValueError:
        pass

    try:
        return Decimal128(value)
    except ValueError:
        pass

    return None


def _maybeOptional(value):
    if isinstance(value, Decimal128):
        return value.to_decimal()

    return value


def _receiptGet():
    session = Session(['debug'])

    id = request.args.get('id')
    if not id:
        return ({"error": "No id provided in request"}, 400)

    pipeline = [
        { "$match" : { "_id" : ObjectId(id) } }
    ]

    assets = list(db.get_db().assets.aggregate(pipeline))
    if not assets:
        return ({"error": "Could not find asset"}, 404)

    asset = Asset(**assets[0])
    data = dict()

    if isinstance(asset.pricing, AssetPricingQuotes) and asset.pricing.quoteId is not None:
        quote = list(db.get_db().quotes.aggregate([
            {'$match': {'_id': ObjectId(asset.pricing.quoteId)}},
            {'$project': {'lastQuote': {'$last': '$quoteHistory.quote'}}}
        ]))
        if quote and 'lastQuote' in quote[0]:
            data['lastQuote'] = quote[0]['lastQuote']

    if asset.currency.name != current_app.config['MAIN_CURRENCY']:
        quote = list(db.get_db().quotes.aggregate([
            {'$match': {'_id': ObjectId(asset.currency.quoteId)}},
            {'$project': {'lastQuote': {'$last': '$quoteHistory.quote'}, 'currencyPair': 1}}
        ]))
        if quote:
            lastQuote = quote[0]['lastQuote']
            if quote[0]['currencyPair']['to'] != asset.currency.name:
                lastQuote = typing.CurrencyConversion.staticConvert(asset.currency.name, quote[0]['currencyPair']['to'], lastQuote)
            data['lastCurrencyRate'] = lastQuote


    data['depositAccounts'] = list(db.get_db().assets.aggregate([
        {'$match': {
            'trashed': {'$ne': True},
            'type': 'Deposit',
            'category': 'Cash',
            '_id': {'$ne': asset.id},
            'currency.name': {'$in': [asset.currency.name, current_app.config['MAIN_CURRENCY']]},
        }}
    ]))

    suggestedDate = datetime.now()
    operationDates = list(set([op.date.time() for op in asset.operations]))
    if len(operationDates) == 1:
        suggestedDate = suggestedDate.replace(hour=operationDates[0].hour, minute=operationDates[0].minute, second=operationDates[0].second)

    data['suggestedDate'] = suggestedDate.strftime('%Y-%m-%d %H:%M:%S')

    return render_template("assets/receipt.html",
                           asset=asset,
                           data=data,
                           header=header.data())


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

    if operation['type'] != typing.Operation.Type.earning or asset.type == AssetType.deposit:
        operation['quantity'] = _parseNumeric(_required("quantity", 102))

    if asset.type == AssetType.deposit:
        if operation['type'] == typing.Operation.Type.receive:
            raise ReceiptError(10, "Deposit asset does not support RECEIVE")

    typeForAdjustment = operation['type']
    if asset.type == AssetType.deposit and operation['type'] == typing.Operation.Type.earning:
        typeForAdjustment = typing.Operation.Type.buy

    quantityForAdjustment = operation['quantity'] if 'quantity' in operation else 0
    operation['finalQuantity'] = typing.Operation.adjustQuantity(typeForAdjustment,
                                                                 asset.finalQuantity,
                                                                 _maybeOptional(quantityForAdjustment))


    if operation['finalQuantity'] < 0:
        raise ReceiptError(11, "Final quantity after operation cannot be less than zero")

    if asset.type == AssetType.deposit:
        operation['price'] = operation['quantity']  # for Deposit type, default unit price is 1
    else:
        operation['price'] = _parseNumeric(_required("price", 103))

    provisionSupportTypes = [typing.Operation.Type.buy, typing.Operation.Type.sell, typing.Operation.Type.earning]
    if 'provision' in request.form and request.form['provision'] != "" and operation['type'] in provisionSupportTypes:
        operation['provision'] = _parseNumeric(request.form['provision'])

    if asset.currency.name != current_app.config['MAIN_CURRENCY']:
        operation['currencyConversion'] = _parseNumeric(_required('currencyConversion', 104))

    if asset.hasOrderIds:
        operation['orderId'] = _required('orderId', 105)

    return operation


def _makeBillingOperation(asset, operation, session):
    if 'billingAsset' not in request.form or not request.form['billingAsset']:
        return None, None

    billingSupportTypes = [typing.Operation.Type.buy, typing.Operation.Type.sell, typing.Operation.Type.earning]
    if operation['type'] not in billingSupportTypes:
        raise ReceiptError(200, "Unsupported operation type for billing asset")

    if operation['type'] == typing.Operation.Type.earning and asset.type == AssetType.deposit:
        raise ReceiptError(201, "EARNING on Deposit does not support billing")

    try:
        query = {'_id': ObjectId(_required('billingAsset', 203))}
    except bson.errors.InvalidId:
        raise ReceiptError(202, "Invalid billingAsset id")

    billingAssets = list(db.get_db().assets.aggregate([{'$match': query}], session=session))

    if not billingAssets:
        raise ReceiptError(203, "Unknown billing asset id")

    billingAsset = Asset(**billingAssets[0])
    if billingAsset.type != AssetType.deposit:
        raise ReceiptError(204, "Billing asset must be a Deposit")

    billingOperation = {
        'date': operation['date'],
        'type': typing.Operation.Type.reverse(operation['type']),
        'quantity': operation['price']
    }

    if billingAsset.currency.name != current_app.config['MAIN_CURRENCY']:
        assert 'currencyConversion' in operation  # checked already at code(104)
        billingOperation['currencyConversion'] = operation['currencyConversion']

    if asset.currency != billingAsset.currency:
        assert 'currencyConversion' in operation  # checked already at code(104)
        if billingAsset.currency.name != current_app.config['MAIN_CURRENCY']:
            raise ReceiptError(205, "Invalid billing asset currency")
        # if operation was in foreign currency then billing asset currency can only be the same or main
        # and here we know that the operation currency and billing asset currency are different

        billingOperation['quantity'] = billingOperation['quantity'] * _maybeOptional(operation['currencyConversion'])

    if 'provision' in operation:
        billingOperation['quantity'] = typing.Operation.adjustQuantity(operation['type'],
                                                                       billingOperation['quantity'],
                                                                       operation['provision'])

    billingOperation['quantity'] = round(billingOperation['quantity'], current_app.config['MAIN_CURRENCY_DECIMALS'])

    billingOperation['price'] = billingOperation['quantity']
    billingOperation['finalQuantity'] = typing.Operation.adjustQuantity(billingOperation['type'],
                                                                        billingAsset.finalQuantity,
                                                                        billingOperation['quantity'])

    if billingOperation['finalQuantity'] < 0:
        raise ReceiptError(206, "Not enough asset quantity for billing operation")

    billingOperation['finalQuantity'] = round(billingOperation['finalQuantity'], current_app.config['MAIN_CURRENCY_DECIMALS'])

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
    ], session=session))

    if not assets:
        return ({"error": True, "message": "Unknown asset id", "code": 3}, 400)

    asset = Asset(**assets[0])

    try:
        operation = _makeOperation(asset)
    except ReceiptError as e:
        return (e.response(), 400)

    try:
        billingQuery, billingOperation = _makeBillingOperation(asset, operation, session)
    except ReceiptError as e:
        return (e.response(), 400)

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
