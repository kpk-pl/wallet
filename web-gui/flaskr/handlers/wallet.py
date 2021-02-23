from flask import render_template, request, json
from flaskr import db, analyzer, quotes
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from multiprocessing import Pool


def _getQuote(item):
    return (item[0], quotes.getQuote(item[1]))


def wallet():
    if request.method == 'GET':
        queryLiveQuotes = (request.args.get('liveQuotes') == 'true')
        threeMonthsAgo = datetime.now() - relativedelta(months=3)
        threeMonthsAgo = threeMonthsAgo.replace(tzinfo=timezone.utc).timestamp()

        pipeline = [
            {
                "$match" : {
                    "operations": { "$exists": True }
                 }
            },
            {
                "$addFields" : {
                    "finalQuantity": { "$last": "$operations.finalQuantity" },
                    "lastQuote": { "$last": "$quoteHistory" },
                    "quotesAfter3m": { "$filter": {
                             "input": "$quoteHistory",
                             "as": "item",
                             "cond": { "$gte": ["$$item.timestamp", threeMonthsAgo] }
                    }}
                }
            },
            {
                "$addFields" : {
                    "quote3mAgo": { "$first": "$quotesAfter3m" }
                }
            },
            { "$match" : { "finalQuantity": { "$ne": 0 } } },
            { "$unset" : ["quoteHistory", "quotesAfter3m"] }
        ]
        assets = [analyzer.Analyzer(asset) for asset in db.get_db().assets.aggregate(pipeline)]

        currenciesPipeline = [
            { "$addFields" : { "lastQuote": { "$last": "$quoteHistory" } } },
            { "$unset" : "quoteHistory" }
        ]
        currencies = { c['name'] : c for c in db.get_db().currencies.aggregate(currenciesPipeline) }

        if queryLiveQuotes:
            liveQuotes = { a.data['name'] : a.data['link'] for a in assets if 'link' in a.data }
            liveCurrencies = { "__currency_" + name : c['link'] for name, c in currencies.items()}
            liveQuotes = {**liveQuotes, **liveCurrencies}

            with Pool(len(assets)) as pool:
                liveQuotes = dict(pool.map(_getQuote, liveQuotes.items()))

            for name in currencies.keys():
                currencies[name]['lastQuote'] = liveQuotes["__currency_" + name]
            for asset in assets:
                if asset.data['name'] in liveQuotes:
                    asset.data['lastQuote'] = liveQuotes[asset.data['name']]

        for currency in currencies.keys():
            currencies[currency] = currencies[currency]['lastQuote']

        for asset in assets:
            asset.addQuoteInfo(currencies)

        categoryAllocation = {}
        for asset in assets:
            if asset.data['category'] not in categoryAllocation:
                categoryAllocation[asset.data['category']] = asset.data['_netValue']
            else:
                categoryAllocation[asset.data['category']] += asset.data['_netValue']

        assets = sorted([a.data for a in assets], key=lambda a: a['name'].lower())
        return render_template("wallet.html", assets=assets, allocation=json.dumps(categoryAllocation))
