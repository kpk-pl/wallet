from flask import request, render_template, jsonify
from flaskr import db, header, stooq
from flaskr.model.quote import QuoteUpdateFrequency, QuoteCurrencyPair
from flaskr.apps.quotes.list import listIds as listActiveQuoteIds
from flaskr.quotes import Fetcher as QuotesFetcher
from pydantic import BaseModel, HttpUrl, ValidationError, Field
from typing import Optional


class PostData(BaseModel):
    name: str
    unit: str
    ticker: Optional[str]
    url: HttpUrl
    updateFrequency: QuoteUpdateFrequency
    currencyPairCheck: bool = Field(False, exclude=True)


def postNewItem():
    try:
        model = PostData(**request.form)
    except ValidationError:
        return ({'error': True, 'code': 1, 'message': "Invalid request"}, 400)

    data = model.dict(exclude_none=True)

    if stooq.Stooq.isValidUrl(model.url):
        data['stooqSymbol'] = stooq.Stooq(url=model.url).ticker

    if model.currencyPairCheck:
        if 'currencyPairFrom' not in request.form.keys() or not model.unit:
            return ({'error': True, 'code': 2, 'message': "Invalid request"}, 400)

        # Yes, this is reversed in the application logic
        # The way it was designed is that you need to pay a quote ammount of 'from' currency to convert it to 1 'to'.
        # So having currency pair 'from': 'PLN', 'to': 'EUR', we take a quote (4.5) of 'PLN' to buy 1 'EUR'
        data['currencyPair'] = QuoteCurrencyPair(
            destination = request.form['currencyPairFrom'],
            source = model.unit
        )

    try:
        quote = QuotesFetcher(model.url).fetch()
        data['quoteHistory'] = [dict(
           timestamp=quote.timestamp,
           quote=float(quote.quote)
        )]
    except:
        pass

    addedId = db.get_db().quotes.insert(data)
    return {'ok': True, 'id': str(addedId)}


def _getPipeline(includeTrashed = False):
    pipeline = []

    if not includeTrashed:
        pipeline.append({'$match': {'trashed': {'$ne': True}}})

    pipeline.append({'$project': {
            '_id': 1,
            'name': 1,
            'url': 1,
            'unit': 1,
            'trashed': 1,
            'currencyPair': 1,
            'lastQuote': {'$last': '$quoteHistory'}
        }})

    return pipeline

def listAll():
    if request.method == 'GET':
        includeTrashed = 'all' in request.args
        sources = list(db.get_db().quotes.aggregate(_getPipeline(includeTrashed)))

        activeQuoteIds = listActiveQuoteIds(used=True)
        for source in sources:
            source['active'] = source['_id'] in activeQuoteIds

        return render_template("pricing/list.html", sources=sources, header=header.data())

    elif request.method == 'POST':
        return postNewItem()
