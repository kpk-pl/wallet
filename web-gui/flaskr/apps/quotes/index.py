from flask import request, Response, json
from flaskr import db
from flaskr.quotes import getQuote
from datetime import datetime
from multiprocessing import Pool


def _getQuote(item):
    return (item[0], getQuote(item[1]))


def _getPipelineForAssets():
    pipeline = []
    pipeline.append({'$match': {
        'pricing.quoteId': {'$exists': True},
        'trashed': {'$ne': True}
    }})
    pipeline.append({'$project': {
        'quoteId': '$pricing.quoteId',
        'currencyId': '$currency.quoteId'
    }})
    return pipeline


def _getPipelineForQuoteUrls(ids):
    pipeline = []
    pipeline.append({'$match': {'_id': {'$in': list(ids)}}}),
    pipeline.append({'$project': {
        '_id': 1,
        'name': 1,
        'url': 1,
        'lastQuote': {'$last': '$quoteHistory'}
    }})
    return pipeline


def index():
    if request.method in ['GET', 'PUT']:
        storeQuotes = (request.method == 'PUT')

        assetInfo = list(db.get_db().assets.aggregate(_getPipelineForAssets()))
        ids = set(obj['quoteId'] for obj in assetInfo) | set(obj['currencyId'] for obj in assetInfo if 'currencyId' in obj)

        quotesIds = list(db.get_db().quotes.aggregate(_getPipelineForQuoteUrls(ids)))
        liveQuotes = { e['_id'] : e['url'] for e in quotesIds }

        with Pool(4) as pool:
            liveQuotes = dict(pool.map(_getQuote, liveQuotes.items()))

        response = []
        for quote in quotesIds:
            _id = quote['_id']
            liveQuote = liveQuotes[_id]
            stale = quote['lastQuote']['timestamp'] == liveQuote['timestamp']
            if not stale:
                if storeQuotes:
                    query = {'_id': _id}
                    update = {'$push': {'quoteHistory': {
                        'timestamp': liveQuote['timestamp'],
                        'quote': liveQuote['quote']
                    }}}
                    db.get_db().quotes.update(query, update)
            else:
                liveQuote['stale'] = True

            response.append({'name': quote['name'], 'quote': liveQuote})

        return Response(json.dumps(response), mimetype="application/json")
