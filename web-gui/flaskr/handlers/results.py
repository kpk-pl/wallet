from flask import render_template, request
from flaskr import db, analyzer
import time
from datetime import datetime, date


def _getPipeline(year):
    pipeline = []

    nextYear = datetime(year + 1, 1, 1)

    # include only those assets that were created up to this year
    pipeline.append({ '$match': { "operations.0.date": {'$lte': nextYear}}})

    firstDay = datetime(year, 1, 1)
    pipeline.append({ '$project': {
        '_id': 0,
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
            'cond': {'$lte': ['$$op.date', nextYear]}
        }},
        'quoteHistory': { '$filter': {
            'input': '$quoteHistory',
            'as': 'q',
            'cond': { '$and': [
                { '$gte': ['$$q.timestamp', firstDay] },
                { '$lt': ['$$q.timestamp', nextYear] }
            ]}
        }}
    }})

    pipeline.append({ '$addFields': {
        'finalQuantity': { '$last': '$operations.finalQuantity' },
        'lastQuote': { '$last' : '$quoteHistory' }
    }})

    return pipeline


def _getCurrencyPipeline(year):
    pipeline = []

    firstDay = datetime(year, 1, 1)
    nextYear = datetime(year + 1, 1, 1)
    pipeline.append({ '$project': {
        '_id': 0,
        'name': 1,
        'quoteHistory': { '$filter': {
            'input': '$quoteHistory',
            'as': 'q',
            'cond': { '$and': [
                { '$gte': ['$$q.timestamp', firstDay] },
                { '$lt': ['$$q.timestamp', nextYear] }
            ]}
        }}
    }})

    return pipeline


def results(year):
    if request.method == 'GET':
        assets = [analyzer.Analyzer(asset) for asset in db.get_db().assets.aggregate(_getPipeline(year))]
        currencies = { c['name'] : c for c in db.get_db().currencies.aggregate(_getCurrencyPipeline(year)) }

        for asset in assets:
            asset.addPeriodInfo(datetime(year, 1, 1), datetime(year+1, 1, 1), currencies)
