from flask import render_template, request, Response, json, jsonify
from flaskr import db, quotes
from flaskr.analyzers.profits import Profits
from bson.objectid import ObjectId
from dateutil import parser
from datetime import datetime, timedelta
from flaskr.stooq import Stooq
from flaskr.pricing import PricingContext, Pricing


def parseNumeric(value):
    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        pass

    return None


def _getPipelineForAssetDetails(assetId):
    pipeline = []
    pipeline.append({ "$match" : { "_id" : ObjectId(assetId) } })
    pipeline.append({ "$project" : {
        "name": 1,
        "institution": 1,
        "category": 1,
        "subcategory": 1,
        "currency": 1,
        "type": 1,
        "pricing": 1,
        "link": 1,
        "operations": { "$ifNull": [ '$operations', [] ] },
        "finalQuantity": { "$last": "$operations.finalQuantity" }
    }})
    return pipeline


def _getPipelineForAssetQuotes(quoteId):
    pipeline = []
    pipeline.append({'$match' : { '_id' : quoteId }})
    pipeline.append({'$project' : { 'quoteHistory' : 1 }})
    return pipeline


def asset():
    if request.method == 'GET':
        assetId = request.args.get('id')
        if not assetId:
            return ('', 400)

        assets = list(db.get_db().assets.aggregate(_getPipelineForAssetDetails(assetId)))
        if not assets:
            return ('', 404)

        asset = Profits(assets[0])()

        if 'quoteId' in asset['pricing']:
            quoteHistory = list(db.get_db().quotes.aggregate(_getPipelineForAssetQuotes(asset['pricing']['quoteId'])))
            if quoteHistory:
                asset['quoteHistory'] = quoteHistory[0]['quoteHistory']

        lastQuoteUpdateTime = db.last_quote_update_time()
        misc = {
            'lastQuoteUpdate': {
                'timestamp': lastQuoteUpdateTime,
                'daysPast': (datetime.now() - lastQuoteUpdateTime).days
            }
        }

        return render_template("asset/_.html", asset=asset, misc=misc)
    elif request.method == 'POST':
        data = {}

        allowedKeys = ['name', 'ticker', 'currency', 'link', 'type', 'category', 'subcategory', 'region', 'institution']
        for key in allowedKeys:
            if key in request.form.keys() and request.form[key]:
                data[key] = request.form[key]

        if data['link'].startswith("https://stooq.pl"):
            data['stooqSymbol'] = Stooq(url=data['link']).ticker

        addedId = db.get_db().assets.insert(data)
        return jsonify(id=str(addedId))


def asset_add():
    if request.method == 'GET':
        lastQuoteUpdateTime = db.last_quote_update_time()
        misc = {
            'lastQuoteUpdate': {
                'timestamp': lastQuoteUpdateTime,
                'daysPast': (datetime.now() - lastQuoteUpdateTime).days
            }
        }

        return render_template("asset/add.html", misc=misc)


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
        return render_template("asset/receipt.html", asset=asset)

    elif request.method == 'POST':
        operation = {
            'date': parser.parse(request.form['date']),
            'type': request.form['type'],
            'quantity': parseNumeric(request.form['quantity']),
            'finalQuantity': parseNumeric(request.form['finalQuantity']),
            'price': float(request.form['price'])
        }

        provision = request.form['provision']
        if provision:
            provision = float(provision)
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


def _getPipelineForIdsHistorical(ids):
    pipeline = [
        { "$match" : { "_id" : { "$in": [ObjectId(id) for id in ids] } } },
        { "$project" : {
            '_id': 1,
            'operations': 1,
            'currency': 1,
            'name': 1,
            'category': 1,
            'subcategory': 1,
            'pricing': 1
        }}
    ]
    return pipeline


def _responseForSingleAssetHistoricalValue(asset):
    raise NotImplementedError()
    currencyData = currencies[asset['currency']] if asset['currency'] != 'PLN' else None
    historical = HistoricalValue(asset, currencyData)
    values = historical()
    result = {
        'name': asset['name'],
        'currency': 'PLN',
        'category': asset['category'],
        'subcategory': asset['subcategory'] if 'subcategory' in asset else None,
        't': values['t'],
        'y': values['y']
    }
    return Response(json.dumps(result), mimetype="application/json")


def asset_historicalValue():
    if request.method == 'GET':
        ids = request.args.getlist('id')
        if not ids:
            return ('', 400)

        ids = list(set(ids))

        daysBack = request.args.get('daysBack')
        daysBack = int(daysBack) if daysBack is not None else int(1.5*365)

        now = datetime.now()
        pricingCtx = PricingContext(finalDate = now, startDate = now - timedelta(daysBack))
        pricing = Pricing(pricingCtx)

        inPercent = request.args.get('inPercent') is not None

        assets = list(db.get_db().assets.aggregate(_getPipelineForIdsHistorical(ids)))
        if len(assets) != len(ids):
            return ('', 404)

        if len(assets) == 1:
            return _responseForSingleAssetHistoricalValue(assets[0])

        result = {'t': pricingCtx.timeScale, 'categories': {}}
        for asset in assets:
            key = asset['category']
            if 'subcategory' in asset:
                key += ' ' + asset['subcategory']

            if key not in result['categories']:
                result['categories'][key] = {
                    'y': None,
                    'names': [],
                    'category': asset['category'],
                    'subcategory': asset['subcategory'] if 'subcategory' in asset else None,
                }

            bucket = result['categories'][key]

            bucket['names'].append(asset['name'])

            values = pricing.priceAssetHistory(asset)
            if bucket['y'] is None:
                bucket['y'] = values['y']
            else:
                assert len(bucket['y']) == len(values['y'])
                bucket['y'] = [a + b for a, b in zip(bucket['y'], values['y'])]

        if inPercent:
            for idx in range(len(result['t'])):
                categorySum = sum([category['y'][idx] for _, category in result['categories'].items()])
                for _, category in result['categories'].items():
                    category['y'][idx] /= categorySum / 100

        return Response(json.dumps(result), mimetype="application/json")


def asset_trash():
    if request.method == 'POST':
        assetId = request.args.get('id')
        if not assetId:
            return ('', 400)

        query = {'_id': ObjectId(assetId)}
        update = {'$set': {'trashed': True}}
        db.get_db().assets.update(query, update)

        return Response()
