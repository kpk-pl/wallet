from flask import request, Response, json
from flaskr import db
from flaskr.model import Quote
from flaskr.quotes import Fetcher
from flaskr.utils import simplifyModel, clamp
from datetime import datetime
from multiprocessing import Pool
from bson.objectid import ObjectId
from .list import listIds


def _getQuote(item):
    _id, (url, unit) = item
    try:
        return (_id, Fetcher(url).fetch(unit))
    except Exception as e:
        return (_id, e)


def _getPipelineForQuoteUrls(ids):
    pipeline = []
    pipeline.append({'$match': {'_id': {'$in': list(ids)}}}),
    pipeline.append({'$project': {
        '_id': 1,
        'name': 1,
        'urls': 1,
        'url': 1,
        'unit': 1,
        'updateFrequency': 1,
        # Only the last entry is needed (Quote.lastQuote) — keep the doc light.
        'quoteHistory': {'$slice': ['$quoteHistory', -1]}
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

        quotes = [Quote(**doc) for doc in db.get_db().quotes.aggregate(_getPipelineForQuoteUrls(ids))]
        liveQuotes = { quote.id : (quote.url, quote.unit) for quote in quotes }

        with Pool(threads) as pool:
            liveQuotes = dict(pool.map(_getQuote, liveQuotes.items()))

        response = []
        for quote in quotes:
            _id = quote.id
            liveQuote = liveQuotes[_id]

            if isinstance(liveQuote, Exception):
                if storeQuotes:
                    db.get_db().price_feed_errors.insert_one(dict(
                        pricingId = _id,
                        name = quote.name,
                        timestamp = datetime.now(),
                        trigger = request.url,
                        error = str(liveQuote)
                    ))

                response.append({'name': quote.name, 'error': str(liveQuote)})
            else:
                lastQuote = quote.lastQuote
                stale = lastQuote is not None and lastQuote.timestamp == liveQuote.timestamp
                if not stale:
                    if storeQuotes:
                        query = {'_id': _id}
                        update = {'$push': {'quoteHistory': {
                            'timestamp': liveQuote.timestamp,
                            'quote': float(liveQuote.quote)
                        }}}
                        db.get_db().quotes.update_one(query, update)

                responseQuote = simplifyModel(liveQuote.model_dump(exclude_none=True))
                if stale:
                    responseQuote['stale'] = True

                response.append({'name': quote.name, 'quote': responseQuote})

        return Response(json.dumps(response), mimetype="application/json")


def indexUrl():
    if request.method == 'GET':
        quote = Fetcher(request.args.get('url')).fetch()
        responseJson = json.dumps(simplifyModel(quote.model_dump(exclude_none=True)))
        return Response(responseJson, mimetype="application/json")
