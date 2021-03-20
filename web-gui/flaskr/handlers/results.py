from flask import render_template, request
from flaskr import db
from flaskr.analyzers.profits import Profits
from flaskr.analyzers.period import Period
import time
from datetime import datetime, date
from bson.objectid import ObjectId


def _getPipeline(year):
    pipeline = []

    nextYear = datetime(year + 1, 1, 1)

    # include only those assets that were created up to this year
    pipeline.append({ '$match': { "operations.0.date": {'$lte': nextYear}}})

#    pipeline.append({ "$match" : { "_id" : ObjectId("60153b027e1237164d0e0f97") } })
    pipeline.append({ '$project': {
        '_id': 1,
        'name': 1,
        'ticker': 1,
        'institution': 1,
        'currency': 1,
        'link': 1,
        'category': 1,
        'subcategory': 1,
        'type' : 1,
        'subcategory': 1,
        'operations': { '$filter': {
            'input': '$operations',
            'as': 'op',
            'cond': {'$lte': ['$$op.date', nextYear]}
        }},
        'quoteHistory': { '$filter': {
            'input': '$quoteHistory',
            'as': 'q',
            'cond': { '$and': [
                { '$gte': ['$$q.timestamp', datetime(year-1, 12, 27)] },
                { '$lt': ['$$q.timestamp', datetime(year+1, 1, 5)] }
            ]}
        }}
    }})

#    pipeline.append({ '$addFields': {
#        'finalQuantity': { '$last': '$operations.finalQuantity' },
#        'lastQuote': { '$last' : '$quoteHistory' }
#    }})

    return pipeline


def _getCurrencyPipeline(year):
    pipeline = []

    pipeline.append({ '$project': {
        '_id': 1,
        'name': 1,
        'quoteHistory': { '$filter': {
            'input': '$quoteHistory',
            'as': 'q',
            'cond': { '$and': [
                { '$gte': ['$$q.timestamp', datetime(year-1, 12, 27)] },
                { '$lt': ['$$q.timestamp', datetime(year+1, 1, 5)] }
            ]}
        }}
    }})

    return pipeline


def results(year):
    if request.method == 'GET':
        assets = [Profits(asset)() for asset in db.get_db().assets.aggregate(_getPipeline(year))]
        currencies = { c['name'] : c for c in db.get_db().currencies.aggregate(_getCurrencyPipeline(year)) }

        periodEnd = min(datetime(year+1, 1, 1), datetime.now())

        for asset in assets:
            period = Period(asset, currencies)
            period.calc(datetime(year, 1, 1), periodEnd)

        return render_template("results.html", year=year, assets=assets)
