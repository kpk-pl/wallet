from flask import Flask, request, render_template, Response
from pymongo import MongoClient
from bson.son import SON
from bson.objectid import ObjectId
from multiprocessing import Pool
import quotes, analyzer
import json
import time
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from dateutil import parser
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


@app.route('/wallet', methods = ['GET'])
def wallet():
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
    assets = [analyzer.Analyzer(asset) for asset in db.assets.aggregate(pipeline)]

    currenciesPipeline = [
        { "$addFields" : { "lastQuote": { "$last": "$quoteHistory" } } },
        { "$unset" : "quoteHistory" }
    ]
    currencies = { c['name'] : c for c in db.currencies.aggregate(currenciesPipeline) }

    if queryLiveQuotes:
        liveQuotes = { a.data['name'] : a.data['link'] for a in assets if 'link' in a.data }
        liveCurrencies = { "__currency_" + name : c['link'] for name, c in currencies.items()}
        liveQuotes = {**liveQuotes, **liveCurrencies}

        with Pool(len(assets)) as pool:
            liveQuotes = dict(pool.map(getQuote, liveQuotes.items()))

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


@app.route('/realized-profits')
def realizedProfits():
    pipeline = [
        { '$match': { 'operations': {'$elemMatch': {'type': "SELL"}}}}
    ]

    assets = [analyzer.Analyzer(asset) for asset in db.assets.aggregate(pipeline)]
    assets = sorted([a.data for a in assets], key=lambda a: a['name'].lower())
    return render_template("realized-profits.html", assets=assets)

@app.route('/summary/<int:year>')
def summaryInYear():
    pipeline = [
      { '$match': { "operations.0.date": {'$gte': ISODate(f'{year}-01-01')}}},
      { '$project': {
          'name': 1,
          'ticker': 1,
          'institution': 1,
          'currency': 1,
          'link': 1,
          'category': 1,
          'subcategory': 1,
          'operations': { '$filter': {
              'input': '$operations',
              'as': 'op',
              'cond': {'$lt': ['$$op.date', ISODate(f'{year}-12-31')]}
          }},
          'quoteHistory': { '$filter': {
              'input': '$quoteHistory',
              'as': 'q',
              'cond': { '$and': [
                  { '$gt': ['$$q.timestamp', 1600] },
                  { '$lt': ['$$q.timestamp', 100] }
              ]}
          }}
      }}
    ]

@app.route('/asset/add', methods = ['GET'])
def assetAdd():
    return render_template("asset-add.html")

@app.route('/asset', methods = ['POST'])
def assetPost():
    data = {}

    allowedKeys = ['name', 'ticker', 'currency', 'link', 'type', 'category', 'subcategory', 'region', 'institution']
    for key in allowedKeys:
        if key in request.form.keys() and request.form[key]:
            data[key] = request.form[key]

    db.assets.insert(data)
    return ('', 204)

@app.route('/asset/receipt', methods = ['GET'])
def assetReceiptGet():
    id = request.args.get('id')
    if not id:
        return ('', 400)

    pipeline = [
        { "$match" : { "_id" : ObjectId(id) } },
        {
            "$addFields" : {
                "finalQuantity": { "$last": "$operations.finalQuantity" },
            }
        },
        { "$unset" : ["quoteHistory"] }
    ]

    assets = list(db.assets.aggregate(pipeline))
    if not assets:
        return ('', 404)

    asset = assets[0]
    if 'link' in asset:
        asset['lastQuote'] = quotes.getQuote(asset['link'])
    return render_template("asset-receipt.html", asset=asset)

@app.route('/asset/receipt', methods = ['POST'])
def assetReceiptPost():
    operation = {
        'date': parser.parse(request.form['date']),
        'type': request.form['type'],
        'quantity': float(request.form['quantity']),
        'finalQuantity': float(request.form['finalQuantity']),
        'price': float(request.form['price'])
    }

    provision = float(request.form['provision'])
    if provision > 0:
        operation['provision'] = provision

    if 'currencyConversion' in request.form.keys():
        operation['currencyConversion'] = float(request.form['currencyConversion'])


    query = {'_id': ObjectId(request.form['_id'])}
    update = {'$push': {'operations': operation }}

    if request.form['type'] == 'BUY':
        asset = db.assets.find_one(query)
        if asset and 'quoteHistory' not in asset:
            update['$push']['quoteHistory'] = {
                'timestamp': operation['date'].timestamp(),
                'quote': operation['price'] / operation['quantity']
            }

    db.assets.update(query, update)
    return ('', 204)

@app.route('/quote', methods = ['GET'])
def quote():
    quoteUrl = request.args.get('url')
    response = quotes.getQuote(quoteUrl)
    return Response(json.dumps(response), mimetype="application/json")


@app.route('/quotes', methods = ['GET', 'PUT'])
def saveQuotes():
    storeQuotes = (request.method == 'PUT')

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
