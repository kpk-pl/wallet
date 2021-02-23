from flask import request, Response, json
from flaskr import db
from flaskr.quotes import getQuote
import time
from multiprocessing import Pool


def _getQuote(item):
    return (item[0], getQuote(item[1]))


def quotes():
    if request.method in ['GET', 'PUT']:
        storeQuotes = (request.method == 'PUT')

        assets = list(db.get_db().assets.find({'link': {'$exists': True}}, {'_id': 1, 'name': 1, 'link': 1}))
        assetDict = { e['_id'] : e['link'] for e in assets }

        currencies = list(db.get_db().currencies.find({}, {'_id': 1, 'name': 1, 'link': 1}))
        currenciesDict = { e['_id'] : e['link'] for e in currencies }

        timestamp = int(time.time())

        quotes = {**assetDict, **currenciesDict}
        with Pool(len(quotes)) as pool:
            quotes = dict(pool.map(_getQuote, quotes.items()))

        response = []
        for asset in assets:
            _id = asset['_id']
            if storeQuotes:
                query = {'_id': _id}
                update = {'$push': {'quoteHistory': {'timestamp': timestamp, 'quote': quotes[_id]['quote']}}}
                db.get_db().assets.update(query, update)
            response.append({'name': asset['name'], 'quote': quotes[_id]})

        for asset in currencies:
            _id = asset['_id']
            if storeQuotes:
                query = {'_id': _id}
                update = {'$push': {'quoteHistory': {'timestamp': timestamp, 'quote': quotes[_id]['quote']}}}
                db.get_db().currencies.update(query, update)
            response.append({'name': asset['name'], 'quote': quotes[_id]})

        return Response(json.dumps(response), mimetype="application/json")
