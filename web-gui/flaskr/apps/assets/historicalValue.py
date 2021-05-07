from flask import request, Response, json
from flaskr import db
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from flaskr.pricing import PricingContext, Pricing


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


def historicalValue():
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
