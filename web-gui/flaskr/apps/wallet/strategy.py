from flask import render_template, request, Response, json

from datetime import datetime
from flaskr import db, header
from flaskr.session import Session
from flaskr.pricing import Pricing
from flaskr.analyzers.categories import Categories
from flaskr.model import Asset, AssetPricingQuotes
from flaskr.utils import jsonify
from decimal import Decimal
from dataclasses import dataclass
from typing import Optional


def _getPipelineFilters(label = None):
    pipeline = []

    match = {
        "operations": { "$exists": True, "$not": { "$size": 0 } }
    }

    if label is not None:
        match['labels'] = label

    pipeline.append({ "$match" : match })
    pipeline.append({ "$addFields" : {
        "finalOperation": { "$last": "$operations" },
    }})

    return pipeline


def _getPipeline(label = None):
    pipeline = _getPipelineFilters(label)
    pipeline.append({ "$match" : {
        'trashed': { '$ne': True },
        "finalOperation.finalQuantity": { "$ne": 0 }
    }})
    pipeline.append({ "$addFields" : {
        "finalQuantity": "$finalOperation.finalQuantity",
    }})

    return pipeline


def _lastStrategyPipeline(label = None):
    return [
        {'$match': {'label': label}},
        {'$sort': {'creationDate': -1}},
        {'$limit': 1},
        {'$project': {
            '_id': 0
        }}
    ]


@dataclass
class StrategyAssetData:
    id: str
    name: str
    institution: str
    category: str
    quantity: Decimal
    unitPrice: Decimal
    currency: str
    currencyConversion: Decimal


def _response(shouldAllocate=False, label=None):
    response = {'label': label}

    strategy = list(db.get_db().strategy.aggregate(_lastStrategyPipeline(label)))
    if strategy:
        response['strategy'] = strategy[0]

    assetData = []
    if shouldAllocate:
        pricing = Pricing()
        assets = list(db.get_db().assets.aggregate(_getPipeline(label)))
        for rawAsset in assets:
            asset = Asset(**rawAsset)
            netValue, quantity = pricing(asset)
            rawAsset['_netValue'] = netValue 

            if asset.pricing is not None and isinstance(asset.pricing, AssetPricingQuotes):
                currencyConversion = pricing.getLastPrice(asset.currency.quoteId, asset.currency.name)
                unitPrice = pricing.getLastPrice(asset.pricing.quoteId)
                if unitPrice is not None:
                    assetData.append(StrategyAssetData(
                        id=str(asset.id),
                        name=asset.name,
                        institution=asset.institution,
                        category=f"{asset.subcategory} {asset.category}" if asset.subcategory else asset.category,
                        quantity=quantity if quantity is not None else Decimal(0),
                        currency=asset.currency.name,
                        currencyConversion=currencyConversion if currencyConversion else Decimal(1),
                        unitPrice=unitPrice
                    ))

        response['allocation'] = Categories()(assets)
        response['assets'] = assetData

    return response


def strategy():
    if request.method == 'GET':
        session = Session(['label'])
        return render_template("wallet/strategy.html", header=header.data(showLabels = True))

    elif request.method == 'POST':
        label = request.args.get('label')
        if not label:
            label = None

        data = json.loads(request.data.decode('utf-8'))

        for entry in data:
            entry['categories'] = [v['name'] if v['percentage'] == 100 else v for v in entry['categories']]

        db.get_db().strategy.insert(dict(
            creationDate = datetime.now(),
            assetTypes = data,
            label = label,
        ))

        return '', 201


def strategy_json():
    if request.method == 'GET':
        shouldAllocate = request.args.get('allocation') == 'true'
        label = request.args.get('label')
        if not label:
            label = None

        try:
            response = _response(shouldAllocate, label)
        except RuntimeError as e:
            return {'error': True, 'message': str(e)}, 400

        if response is None:
            return {'error': True, 'message': "Could not get strategy information"}, 500

        return Response(jsonify(response), mimetype="application/json")
