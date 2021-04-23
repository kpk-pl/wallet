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
        'quoteId': '$pricing.quoteId'
    }})
    return pipeline


def _getPipelineForQuoteUrls(ids):
    pipeline = []
    pipeline.append({'$match': {
        '_id': {'$in': list(ids)}
    }})
    pipeline.append({'$project': {
        '_id': 1,
        'name': 1,
        'url': 1
    }})
    return pipeline

def quotes():
    if request.method in ['GET', 'PUT']:
        storeQuotes = (request.method == 'PUT')

        assetQuoteIds = set(obj['quoteId'] for obj in list(db.get_db().assets.aggregate(_getPipelineForAssets())))
        quotesIds = list(db.get_db().quotes.aggregate(_getPipelineForQuoteUrls(assetQuoteIds)))
        quotesDict = { e['_id'] : e['url'] for e in quotesIds }

        currencies = list(db.get_db().currencies.find({}, {'_id': 1, 'name': 1, 'link': 1}))
        currenciesDict = { e['_id'] : e['link'] for e in currencies }

        quotes = {**quotesDict, **currenciesDict}
        with Pool(4) as pool:
            quotes = dict(pool.map(_getQuote, quotes.items()))

        response = []
        now = datetime.now()

        for asset in quotesIds:
            _id = asset['_id']
            timeDiff = now - quotes[_id]['timestamp']
            if timeDiff.days == 0:
                if storeQuotes:
                    query = {'_id': _id}
                    update = {'$push': {'quoteHistory': {
                        'timestamp': quotes[_id]['timestamp'],
                        'quote': quotes[_id]['quote']
                    }}}
                    db.get_db().quotes.update(query, update)
            else:
                quotes[_id]['stale'] = True

            response.append({'name': asset['name'], 'quote': quotes[_id]})

        for asset in currencies:
            _id = asset['_id']
            timeDiff = now - quotes[_id]['timestamp']
            if timeDiff.days == 0:
                if storeQuotes:
                    query = {'_id': _id}
                    update = {'$push': {'quoteHistory': {
                        'timestamp': quotes[_id]['timestamp'],
                        'quote': quotes[_id]['quote']
                    }}}
                    db.get_db().currencies.update(query, update)
            else:
                quotes[_id]['stale'] = True

            response.append({'name': asset['name'], 'quote': quotes[_id]})

        return Response(json.dumps(response), mimetype="application/json")
