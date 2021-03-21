from flask import render_template, request, json

from flaskr import db, quotes
from flaskr.analyzers.profits import Profits
from flaskr.analyzers.value import Value

from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from multiprocessing import Pool


def _getQuote(item):
    return (item[0], quotes.getQuote(item[1]))


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


def wallet():
    if request.method == 'GET':
        queryLiveQuotes = (request.args.get('liveQuotes') == 'true')
        debug = bool(request.args.get('debug'))

        assets = list(db.get_db().assets.aggregate(_getPipeline()))
        assets = [Profits(asset)() for asset in assets]

        currenciesPipeline = [
            { "$addFields" : { "lastQuote": { "$last": "$quoteHistory" } } },
            { "$unset" : "quoteHistory" }
        ]
        currencies = { c['name'] : c for c in db.get_db().currencies.aggregate(currenciesPipeline) }

        if queryLiveQuotes:
            liveQuotes = { a['name'] : a['link'] for a in assets if 'link' in a }
            liveCurrencies = { "__currency_" + name : c['link'] for name, c in currencies.items()}
            liveQuotes = {**liveQuotes, **liveCurrencies}

            with Pool(len(assets)) as pool:
                liveQuotes = dict(pool.map(_getQuote, liveQuotes.items()))

            for name in currencies.keys():
                currencies[name]['lastQuote'] = liveQuotes["__currency_" + name]
            for asset in assets:
                if asset['name'] in liveQuotes:
                    asset['lastQuote'] = liveQuotes[asset['name']]

        for currency in currencies.keys():
            currencies[currency] = currencies[currency]['lastQuote']

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
