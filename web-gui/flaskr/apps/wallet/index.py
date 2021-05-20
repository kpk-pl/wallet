from flask import render_template, request, json, current_app

from flaskr import db
from flaskr.analyzers.profits import Profits
from flaskr.pricing import Pricing, PricingContext

from bson.objectid import ObjectId

from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from collections import defaultdict


def _getPipelineFilters(label = None):
    pipeline = []

    pipeline.append({ "$match" : {
        "operations": { "$exists": True }
    }})

    if label is not None:
        pipeline.append({ "$match" : {
            'labels': label
        }})

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
    pipeline.append({ "$project" : {
        "_id": 1,
        "name": 1,
        "ticker": 1,
        "institution": 1,
        "category": 1,
        "subcategory": 1,
        "currency": 1,
        "region": 1,
        "operations": 1,
        "pricing": 1,
        "finalQuantity": "$finalOperation.finalQuantity",
    }})

    return pipeline


def _getPipelineRecentlyClosed(label = None):
    pipeline = _getPipelineFilters(label)

    # When changing the history context, change also the html template for 'daysBack'
    pipeline.append({ "$match" : {
        "finalOperation.finalQuantity": 0,
        "finalOperation.date": {
          '$gte': datetime.now() - timedelta(days=41)
        }
    }})

    pipeline.append({ "$project" : { "_id": 1 }})

    return pipeline


def _allLabelsPipeline():
    pipeline = []
    pipeline.append({'$unwind': {
        'path': '$labels',
        'preserveNullAndEmptyArrays': False
    }})
    pipeline.append({'$group': {
        '_id': None,
        'label': {'$addToSet': '$labels'}
    }})

    return pipeline


def index():
    if request.method == 'GET':
        debug = bool(request.args.get('debug'))
        label = request.args.get('label')

        assets = list(db.get_db().assets.aggregate(_getPipeline(label)))
        assets = [Profits(asset)() for asset in assets]

        pricing = Pricing()
   #     pricingQuarterAgoCtx = PricingContext(finalDate = datetime.now() - relativedelta(months=3))
   #     pricingQuarterAgo = Pricing(pricingQuarterAgoCtx)
        for asset in assets:
            currentPrice, _ = pricing.priceAsset(asset)
            asset['_netValue'] = currentPrice

            #quarterAgoPrice = pricingQuarterAgo.priceAsset(asset)
            #if quarterAgoPrice is not None:
            #    asset['_quarterValueChange'] = (currentPrice - quarterAgoPrice) / quarterAgoPrice

        categoryAllocation = defaultdict(lambda: defaultdict(int))
        for asset in assets:
            subcategory = asset['subcategory'] if 'subcategory' in asset else asset['category']
            categoryAllocation[asset['category']][subcategory] += asset['_netValue']

        lastQuoteUpdateTime = db.last_quote_update_time()
        allLabels = list(db.get_db().assets.aggregate(_allLabelsPipeline()))[0]['label']
        recentlyClosedIds = [e['_id'] for e in db.get_db().assets.aggregate(_getPipelineRecentlyClosed(label))]
        misc = {
            'showData': debug,
            'label': label,
            'allLabels': allLabels,
            'recentlyClosedIds': recentlyClosedIds,
            'lastQuoteUpdate': {
                'timestamp': lastQuoteUpdateTime,
                'daysPast': (datetime.now() - lastQuoteUpdateTime).days
            }
        }

        return render_template("index.html",
                               assets=assets,
                               allocation=json.dumps(categoryAllocation),
                               misc=misc)
