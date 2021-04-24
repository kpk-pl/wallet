from flask import render_template, request, json, current_app

from flaskr import db
from flaskr.analyzers.profits import Profits
from flaskr.pricing import Pricing

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
    }})

    return pipeline


def wallet():
    if request.method == 'GET':
        debug = bool(request.args.get('debug'))
        official = bool(request.args.get('official'))

        assets = list(db.get_db().assets.aggregate(_getPipeline(official)))
        assets = [Profits(asset)() for asset in assets]

        pricing = Pricing()
        for asset in assets:
            asset['_netValue'] = pricing.priceAsset(asset)

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
