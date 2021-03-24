from flask import render_template, request, json, current_app

from flaskr import db, quotes
from flaskr.stooq import Stooq
from flaskr.analyzers.profits import Profits
from flaskr.analyzers.value import Value

from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from multiprocessing import Pool


def _getPipeline():
    threeMonthsAgo = datetime.now() - relativedelta(months=3)
    threeMonthsAgo = threeMonthsAgo.replace(tzinfo=timezone.utc)

    pipeline = []

    pipeline.append({ "$match" : {
        "operations": { "$exists": True }
    }})

    pipeline.append({ "$addFields" : {
        "finalQuantity": { "$last": "$operations.finalQuantity" },
        "lastQuote": { "$last": "$quoteHistory" },
        "quotesAfter3m": { "$filter": {
                 "input": "$quoteHistory",
                 "as": "item",
                 "cond": { "$gte": ["$$item.timestamp", threeMonthsAgo] }
        }}
    }})

    pipeline.append({ "$addFields" : {
        "quote3mAgo": { "$first": "$quotesAfter3m" }
    }})

    pipeline.append({ "$match" : { "finalQuantity": { "$ne": 0 } } })
    pipeline.append({ "$unset" : ["quoteHistory", "quotesAfter3m"] })

    return pipeline


def _getCurrencyPipeline():
    pipeline = [
        { "$addFields" : { "lastQuote": { "$last": "$quoteHistory" } } },
        { "$unset" : "quoteHistory" }
    ]

    return pipeline


def _queryLiveQuote(asset):
    if 'stooqSymbol' in asset:
        current_app.logger.info(f"Querying live quotes from stooq: {asset['stooqSymbol']}")
        provider = Stooq(asset['stooqSymbol'])

        now = datetime.now()
        threeMonthsAgo = now - relativedelta(months=3)
        threeMonthsAgo = threeMonthsAgo.replace(tzinfo=timezone.utc)

        data = provider.history(threeMonthsAgo, now)
        print(data)
        asset['lastQuote'] = data[-1]['close']
        asset['quote3mAgo'] = data[0]['close']
    else:
        current_app.logger.info(f"Querying live quotes: {asset['link']}")
        asset['lastQuote'] = quotes.getQuote(asset['link'])


def wallet():
    if request.method == 'GET':
        queryLiveQuotes = (request.args.get('liveQuotes') == 'true')
        debug = bool(request.args.get('debug'))

        assets = list(db.get_db().assets.aggregate(_getPipeline()))
        assets = [Profits(asset)() for asset in assets]

        currencies = list(db.get_db().currencies.aggregate(_getCurrencyPipeline()))

        if queryLiveQuotes:
            objects = [obj for obj in assets + currencies if 'link' in obj]
            with Pool(1) as pool:
                pool.map(_queryLiveQuote, objects)

        currencies = { c['name'] : c['lastQuote'] for c in currencies }

        assets = [Value(asset, currencies)() for asset in assets]

        categoryAllocation = {}
        for asset in assets:
            category = asset['category']
            if 'subcategory' in asset:
                category += " " + asset['subcategory']
            if category not in categoryAllocation:
                categoryAllocation[category] = asset['_netValue']
            else:
                categoryAllocation[category] += asset['_netValue']

        return render_template("wallet.html", assets=assets, allocation=json.dumps(categoryAllocation), showData=debug)
