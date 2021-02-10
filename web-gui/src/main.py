from flask import Flask, request, render_template, Response
from pymongo import MongoClient
from bson.son import SON
from multiprocessing import Pool
import quotes, analyzer
import json
import time
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
import os


mongo = MongoClient('mongodb://{}:{}@{}:{}'.format(os.environ.get("MONGO_USER", "investing"),
                                                   os.environ.get("MONGO_PASS", "investing"),
                                                   os.environ.get("MONGO_HOST", "127.0.0.1"),
                                                   os.environ.get("MONGO_PORT", "27017")))

db = mongo.wallet
app = Flask(__name__)
app.jinja_env.filters['quote'] = lambda u: "'" + u + "'"


def getQuote(item):
    return (item[0], quotes.getQuote(item[1]))


@app.route('/assets', methods = ['GET'])
def assets():
    pipeline = [
        {
            "$addFields" : {
                "finalQuantity": { "$last": "$operations.finalQuantity" }
            }
        },
        { "$unset" : ["quoteHistory", "operations"] }
    ]
    assets = list(db.assets.aggregate(pipeline))
    return render_template("assets.html", assets=assets)


@app.route('/assets/open', methods = ['GET'])
def assetsOpen():
    queryLiveQuotes = (request.args.get('liveQuotes') == 'true')
    threeMonthsAgo = datetime.now() - relativedelta(months=3)
    threeMonthsAgo = threeMonthsAgo.replace(tzinfo=timezone.utc).timestamp()

    pipeline = [
        {
            "$match" : {
                "operations": { "$exists": True },
                "quoteHistory": { "$exists": True }
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
    assets = [analyzer.Analyzer(asset) for asset in db.assets.aggregate(pipeline)]

    currenciesPipeline = [
        { "$addFields" : { "lastQuote": { "$last": "$quoteHistory" } } },
        { "$unset" : "quoteHistory" }
    ]
    currencies = { c['name'] : c for c in db.currencies.aggregate(currenciesPipeline) }

    if queryLiveQuotes:
        liveQuotes = { a.data['name'] : a.data['quoteSource'] for a in assets }
        liveCurrencies = { "__currency_" + name : c['quoteSource'] for name, c in currencies.items()}
        liveQuotes = {**liveQuotes, **liveCurrencies}

        with Pool(len(assets)) as pool:
            liveQuotes = dict(pool.map(getQuote, liveQuotes.items()))

        for name in currencies.keys():
            currencies[name]['lastQuote'] = liveQuotes["__currency_" + name]
        for asset in assets:
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
    return render_template("assets-open.html", assets=assets, allocation=json.dumps(categoryAllocation))


@app.route('/realized-profits')
def realizedProfits():
    pipeline = [
        { '$match': { 'operations': {'$elemMatch': {'type': "SELL"}}}}
    ]

    assets = [analyzer.Analyzer(asset) for asset in db.assets.aggregate(pipeline)]
    assets = sorted([a.data for a in assets], key=lambda a: a['name'].lower())
    return render_template("realized-profits.html", assets=assets)


@app.route('/asset/add', methods = ['GET'])
def assetAdd():
    return render_template("asset-add.html")

@app.route('/asset', methods = ['POST'])
def assetPost():
    if request.method == 'POST':
        data = {}

        allowedKeys = ['name', 'ticker', 'currency', 'link', 'type', 'category', 'subcategory', 'region', 'institution']
        for key in allowedKeys:
            if key in request.form.keys() and request.form[key]:
                data[key] = request.form[key]
        print(data)
        db.assets.insert(data)
        return ('', 204)

@app.route('/quote', methods = ['GET'])
def quote():
    quoteUrl = request.args.get('url')
    response = quotes.getQuote(quoteUrl)
    return Response(json.dumps(response), mimetype="application/json")


@app.route('/quotes')
def saveQuotes():
    storeQuotes = (request.args.get('store') == 'true')

    assets = list(db.assets.find({'link': {'$exists': True}}, {'_id': 1, 'name': 1, 'link': 1}))
    assetDict = { e['_id'] : e['link'] for e in assets }

    currencies = list(db.currencies.find({}, {'_id': 1, 'name': 1, 'link': 1}))
    currenciesDict = { e['_id'] : e['link'] for e in currencies }

    timestamp = int(time.time())

    quotes = {**assetDict, **currenciesDict}
    with Pool(len(quotes)) as pool:
        quotes = dict(pool.map(getQuote, quotes.items()))

    response = []
    for asset in assets:
        _id = asset['_id']
        if storeQuotes:
            query = {'_id': _id}
            update = {'$push': {'quoteHistory': {'timestamp': timestamp, 'quote': quotes[_id]['quote']}}}
            db.assets.update(query, update)
        response.append({'name': asset['name'], 'quote': quotes[_id]})

    for asset in currencies:
        _id = asset['_id']
        if storeQuotes:
            query = {'_id': _id}
            update = {'$push': {'quoteHistory': {'timestamp': timestamp, 'quote': quotes[_id]['quote']}}}
            db.currencies.update(query, update)
        response.append({'name': asset['name'], 'quote': quotes[_id]})

    return Response(json.dumps(response), mimetype="application/json")
