from flask import render_template, request
from flaskr import db
from flaskr.analyzers.profits import Profits
from flaskr.analyzers.period import Period
import time
from datetime import datetime, date
from bson.objectid import ObjectId


def _getPipeline(year):
    nextYear = datetime(year + 1, 1, 1)

    pipeline = []

    # include only those assets that were created up to this year
    pipeline.append({ '$match': { "operations.0.date": {'$lte': nextYear}}})

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
        'pricing': 1,
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
                { '$lt': ['$$q.timestamp', datetime(year+1, 1, 1)] }
            ]}
        }}
    }})

    return pipeline


def _getQuotesPipeline(ids, year):
    pipeline = []
    pipeline.append({'$match': {
        '_id': {'$in': list(ids)}
    }})
    pipeline.append({'$project': {
        '_id': 1,
        'quoteHistory': { '$filter': {
            'input': '$quoteHistory',
            'as': 'q',
            'cond': { '$and': [
                { '$gte': ['$$q.timestamp', datetime(year-1, 12, 27)] },
                { '$lt': ['$$q.timestamp', datetime(year+1, 1, 1)] }
            ]}
        }}
    }})
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
                { '$lt': ['$$q.timestamp', datetime(year+1, 1, 1)] }
            ]}
        }}
    }})

    return pipeline


def results(year):
    if request.method == 'GET':
        raise NotImplementedError("Not implemented /results to the end after moving quotes to a separate collection")

        assets = [Profits(asset)() for asset in db.get_db().assets.aggregate(_getPipeline(year))]
        currencies = { c['name'] : c for c in db.get_db().currencies.aggregate(_getCurrencyPipeline(year)) }

        quoteIds = [asset['pricing']['quoteId'] for asset in assets if 'quoteId' in asset['pricing']]
        quotes = {q['_id']: q for q in list(db.get_db().quotes.aggregate(_getQuotesPipeline(quoteIds, year)))}

        for asset in assets:
            if 'quoteId' in asset['pricing']:
                asset['quoteHistory'] = quotes[asset['pricing']['quoteId']]['quoteHistory']

        periodEnd = min(datetime(year+1, 1, 1), datetime.now())

        for asset in assets:
            period = Period(asset, currencies)
            period.calc(datetime(year, 1, 1), periodEnd)

        return render_template("results.html", year=year, assets=assets)
