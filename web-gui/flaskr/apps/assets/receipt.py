from flask import render_template, request, current_app
from flaskr import db, header, typing
from flaskr.session import Session
from bson.objectid import ObjectId
from bson.decimal128 import Decimal128
import bson.errors
import copy
from datetime import datetime
from dateutil import parser
from flaskr.model import Asset, AssetType, AssetPricingQuotes
from pydantic import ValidationError
from decimal import Decimal, InvalidOperation


def _parseNumeric(value, field, errorCode):
    try:
        return int(value)
    except (ValueError, TypeError):
        pass

    try:
        return Decimal128(value)
    except (ValueError, TypeError, InvalidOperation):
        pass

    # Never return None silently: a non-numeric value (a stray character, a
    # locale comma, an empty paste) used to either crash a downstream
    # comparison with TypeError or get persisted as quantity=None, corrupting
    # every analyzer. Reject it here at the single boundary with a 400.
    raise ReceiptError(errorCode, f"Field '{field}' is not a valid number: {value!r}")


def _handleConversions(operation, field):
    if isinstance(operation[field], Decimal):
        operation[field] = Decimal128(operation[field])


def _simplifyDecimal(value):
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

    # Operations are stored in date-ascending order — this is the invariant
    # enforced by the Asset model validator and assumed by every downstream
    # consumer (pricing, history, analyzers). Reject a back-dated receipt
    # here with a clear code rather than letting the $push succeed and
    # then crash every page on the next load with a ValidationError.
    if asset.operations and operation['date'] < asset.operations[-1].date:
        raise ReceiptError(
            106,
            f"Operation date {operation['date'].isoformat()} is earlier than the "
            f"last recorded operation ({asset.operations[-1].date.isoformat()}). "
            "Operations must be entered in chronological order."
        )

    if operation['type'] != typing.Operation.Type.earning or asset.type == AssetType.deposit:
        operation['quantity'] = _parseNumeric(_required("quantity", 102), "quantity", 107)

    if asset.type == AssetType.deposit:
        if operation['type'] == typing.Operation.Type.receive:
            raise ReceiptError(10, "Deposit asset does not support RECEIVE")

    typeForAdjustment = operation['type']
    if asset.type == AssetType.deposit and operation['type'] == typing.Operation.Type.earning:
        typeForAdjustment = typing.Operation.Type.buy

    quantityForAdjustment = operation['quantity'] if 'quantity' in operation else 0
    operation['finalQuantity'] = typing.Operation.adjustQuantity(typeForAdjustment,
                                                                 asset.finalQuantity,
                                                                 quantityForAdjustment)


    if operation['finalQuantity'] < 0:
        raise ReceiptError(11, "Final quantity after operation cannot be less than zero")

    _handleConversions(operation, 'finalQuantity')

    if asset.type == AssetType.deposit:
        operation['price'] = operation['quantity']  # for Deposit type, default unit price is 1
    else:
        operation['price'] = _parseNumeric(_required("price", 103), "price", 108)

    provisionSupportTypes = [typing.Operation.Type.buy, typing.Operation.Type.sell, typing.Operation.Type.earning]
    if 'provision' in request.form and request.form['provision'] != "" and operation['type'] in provisionSupportTypes:
        operation['provision'] = _parseNumeric(request.form['provision'], "provision", 109)

    if asset.currency.name != current_app.config['MAIN_CURRENCY']:
        operation['currencyConversion'] = _parseNumeric(_required('currencyConversion', 104), "currencyConversion", 110)

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

    # Same date-ordering invariant applies to the billing deposit — the
    # billing op is stamped with the originating op's date, so a backdated
    # main operation also backdates the billing entry.
    if billingAsset.operations and operation['date'] < billingAsset.operations[-1].date:
        raise ReceiptError(
            207,
            f"Billing asset's last operation is on "
            f"{billingAsset.operations[-1].date.isoformat()}, which is later "
            f"than this operation's date {operation['date'].isoformat()}. "
            "Operations on the billing deposit must also be chronological."
        )

    billingOperation = {
        'date': operation['date'],
        'type': typing.Operation.Type.reverse(operation['type']),
        'quantity': _simplifyDecimal(operation['price'])
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

        billingOperation['quantity'] = _simplifyDecimal(billingOperation['quantity']) * _simplifyDecimal(operation['currencyConversion'])

    if 'provision' in operation:
        billingOperation['quantity'] = typing.Operation.adjustBillingQuantity(operation['type'],
                                                                              billingOperation['quantity'],
                                                                              operation['provision'])

    def normalize(d):
        return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()

    if isinstance(billingOperation["quantity"], Decimal):
        billingOperation['quantity'] = normalize(round(billingOperation['quantity'], current_app.config['MAIN_CURRENCY_DECIMALS']))
        _handleConversions(billingOperation, 'quantity')

    billingOperation['price'] = billingOperation['quantity']
    billingOperation['finalQuantity'] = typing.Operation.adjustQuantity(billingOperation['type'],
                                                                        billingAsset.finalQuantity,
                                                                        billingOperation['quantity'])

    if billingOperation['finalQuantity'] < 0:
        raise ReceiptError(206, "Not enough asset quantity for billing operation")


    if isinstance(billingOperation["finalQuantity"], Decimal):
        billingOperation['finalQuantity'] = normalize(round(billingOperation['finalQuantity'], current_app.config['MAIN_CURRENCY_DECIMALS']))
        _handleConversions(billingOperation, 'finalQuantity')

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


def _loadAssetForEdit():
    """Shared validation for the operation-edit GET/POST: resolve the asset and
    the targeted operation index from the query string."""
    id = request.args.get('id')
    if not id:
        raise ReceiptError(1, "No asset id provided")

    try:
        query = {'_id': ObjectId(id)}
    except bson.errors.InvalidId:
        raise ReceiptError(2, "Invalid asset id")

    index = request.args.get('index')
    try:
        index = int(index)
    except (ValueError, TypeError):
        raise ReceiptError(3, "Invalid operation index")

    assets = list(db.get_db().assets.aggregate([{'$match': query}]))
    if not assets:
        raise ReceiptError(4, "Unknown asset id")

    asset = Asset(**assets[0])
    if index < 0 or index >= len(asset.operations):
        raise ReceiptError(5, "Operation index out of range")

    return query, assets[0], asset, index


def _makeEditedFields(asset, index):
    """Parse the editable subset of an operation (date, price, conversion rate,
    provision & tax). Type and volume are intentionally immutable here because
    changing them would invalidate the running finalQuantity of later
    operations."""
    operation = asset.operations[index]
    date = parser.parse(_required("date", 100))

    # Operations are stored in date-ascending order — an invariant enforced by
    # the Asset model and assumed by every downstream consumer (pricing,
    # history, analyzers). Editing a date must keep the edited operation between
    # its neighbours, so reject an out-of-order date here with a clear message.
    previous = asset.operations[index - 1] if index > 0 else None
    following = asset.operations[index + 1] if index + 1 < len(asset.operations) else None
    if previous is not None and date < previous.date:
        raise ReceiptError(
            106,
            f"Operation date {date.isoformat()} is earlier than the preceding "
            f"operation ({previous.date.isoformat()}). Operations must stay in "
            "chronological order."
        )
    if following is not None and date > following.date:
        raise ReceiptError(
            106,
            f"Operation date {date.isoformat()} is later than the following "
            f"operation ({following.date.isoformat()}). Operations must stay in "
            "chronological order."
        )

    fields = {'date': date}

    # Deposits keep price == quantity (an invariant of the Asset model), and the
    # volume is not editable here, so price stays fixed for them.
    if asset.type != AssetType.deposit:
        fields['price'] = _parseNumeric(_required("price", 103), "price", 108)

    provisionSupportTypes = [typing.Operation.Type.buy, typing.Operation.Type.sell, typing.Operation.Type.earning]
    if operation.type.value in provisionSupportTypes:
        if 'provision' in request.form and request.form['provision'] != "":
            fields['provision'] = _parseNumeric(request.form['provision'], "provision", 109)
        else:
            fields['provision'] = Decimal128("0")

    if asset.currency.name != current_app.config['MAIN_CURRENCY']:
        fields['currencyConversion'] = _parseNumeric(_required('currencyConversion', 104), "currencyConversion", 110)

    if asset.hasOrderIds:
        fields['orderId'] = _required('orderId', 105)

    return fields


def _editGet():
    try:
        _, _, asset, index = _loadAssetForEdit()
    except ReceiptError as e:
        return (e.response(), 400)

    return render_template("assets/editReceipt.html",
                           asset=asset,
                           operation=asset.operations[index],
                           index=index,
                           header=header.data())


def _editPost():
    try:
        query, doc, asset, index = _loadAssetForEdit()
        fields = _makeEditedFields(asset, index)
    except ReceiptError as e:
        return (e.response(), 400)

    # Re-validate the whole asset with the edited operation applied so the change
    # can never leave the document inconsistent (date ordering, deposit
    # price==quantity, required currency conversion, ...).
    candidate = copy.deepcopy(doc)
    candidate['operations'][index].update(fields)
    try:
        Asset(**candidate)
    except ValidationError as e:
        return ({"error": True, "message": str(e), "code": 120}, 400)

    update = {f'operations.{index}.{key}': value for key, value in fields.items()}
    db.get_db().assets.update_one(query, {'$set': update})

    return ({"ok": True}, 200)


def receiptEdit():
    if request.method == 'GET':
        return _editGet()
    elif request.method == 'POST':
        return _editPost()
