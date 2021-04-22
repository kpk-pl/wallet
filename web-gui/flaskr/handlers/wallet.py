from flask import render_template, request, json, current_app

from flaskr import db, quotes
from flaskr.analyzers.profits import Profits
from flaskr.analyzers.value import Value

from bson.objectid import ObjectId

from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from collections import defaultdict


def _getPipeline(official):
    threeMonthsAgo = datetime.now() - relativedelta(months=3)
    threeMonthsAgo = threeMonthsAgo.replace(tzinfo=timezone.utc)

    notOfficialList = []
    if official:
        notOfficialList = [
            ObjectId("601535217e1237164d0e0f96"),
            ObjectId("603ff3be723b462707408f07")
        ]

    pipeline = []

    pipeline.append({ "$match" : {
        "_id": { "$nin": notOfficialList },
        "operations": { "$exists": True }
    }})

    pipeline.append({ "$addFields" : {
        "finalQuantity": { "$last": "$operations.finalQuantity" }
    }})

    pipeline.append({ "$match" : { "finalQuantity": { "$ne": 0 } } })

    pipeline.append({ "$addFields" : {
        "quotesAfter3m": { "$filter": {
                 "input": "$quoteHistory",
                 "as": "item",
                 "cond": { "$gte": ["$$item.timestamp", threeMonthsAgo] }
        }}
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
        "finalQuantity": 1,
        "lastQuote": { "$last": "$quoteHistory" },
        "quote3mAgo": { "$first": "$quotesAfter3m" }
    }})

    return pipeline


def _getCurrencyPipeline():
    pipeline = [
        { "$addFields" : { "lastQuote": { "$last": "$quoteHistory" } } },
        { "$unset" : "quoteHistory" }
    ]

    return pipeline


def wallet():
    if request.method == 'GET':
        debug = bool(request.args.get('debug'))
        official = bool(request.args.get('official'))

        assets = list(db.get_db().assets.aggregate(_getPipeline(official)))
        assets = [Profits(asset)() for asset in assets]

        currencies = list(db.get_db().currencies.aggregate(_getCurrencyPipeline()))
        currencies = { c['name'] : c['lastQuote'] for c in currencies }

        assets = [Value(asset, currencies)() for asset in assets]

        categoryAllocation = defaultdict(lambda: defaultdict(int))
        for asset in assets:
            subcategory = asset['subcategory'] if 'subcategory' in asset else asset['category']
            categoryAllocation[asset['category']][subcategory] += asset['_netValue']

        lastQuoteUpdateTime = db.last_quote_update_time()
        misc = {
            'showData': debug,
            'lastQuoteUpdate': {
                'timestamp': lastQuoteUpdateTime,
                'daysPast': (datetime.now() - lastQuoteUpdateTime).days
            }
        }

        return render_template("wallet.html",
                               assets=assets,
                               allocation=json.dumps(categoryAllocation),
                               misc=misc)
