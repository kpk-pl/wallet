from flask import request, Response, json
from flaskr import db
from flaskr.quotes import Fetcher
from flaskr.utils import simplifyModel
from datetime import datetime
from multiprocessing import Pool
from bson.objectid import ObjectId
from .list import listIds


def _getQuote(item):
    try:
        return (item[0], Fetcher(item[1]).fetch())
    except Exception as e:
        return (item[0], e)


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

        threads = 4
        if 'threads' in request.args.keys():
            threads = clamp(int(request.args.get('threads')), 1, 4)

        if request.args.get('id'):
            ids = [ObjectId(i) for i in set(request.args.getlist('id'))]
        else:
            ids = listIds(used=True)

        quotesIds = list(db.get_db().quotes.aggregate(_getPipelineForQuoteUrls(ids)))
        liveQuotes = { e['_id'] : e['url'] for e in quotesIds }

        with Pool(threads) as pool:
            liveQuotes = dict(pool.map(_getQuote, liveQuotes.items()))

        response = []
        for quote in quotesIds:
            _id = quote['_id']
            liveQuote = liveQuotes[_id]

            if isinstance(liveQuote, Exception):
                if storeQuotes:
                    db.get_db().price_feed_errors.insert_one(dict(
                        pricingId = _id,
                        timestamp = datetime.now(),
                        trigger = request.url,
                        error = str(liveQuote)
                    ))

                response.append({'name': quote['name'], 'error': str(liveQuote)})
            else:
                lastQuote = quote['lastQuote'] if 'lastQuote' in quote else None
                stale = lastQuote is not None and lastQuote['timestamp'] == liveQuote.timestamp
                if not stale:
                    if storeQuotes:
                        query = {'_id': _id}
                        update = {'$push': {'quoteHistory': {
                            'timestamp': liveQuote.timestamp,
                            'quote': float(liveQuote.quote)
                        }}}
                        db.get_db().quotes.update(query, update)

                responseQuote = simplifyModel(liveQuote.dict(exclude_none=True))
                if stale:
                    responseQuote['stale'] = True

                response.append({'name': quote['name'], 'quote': responseQuote})

        return Response(json.dumps(response), mimetype="application/json")


def indexUrl():
    if request.method == 'GET':
        quote = Fetcher(request.args.get('url')).fetch()
        responseJson = json.dumps(simplifyModel(quote.dict(exclude_none=True)))
        return Response(responseJson, mimetype="application/json")
