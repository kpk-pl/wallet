from __future__ import annotations
from flask import request, render_template, jsonify
from flaskr import db, header
from flaskr.model import Quote
from flaskr.model.quote import QuoteUpdateFrequency
from flaskr.apps.quotes.list import listIds as listActiveQuoteIds
from flaskr.quotes import Fetcher as QuotesFetcher, FetchError
from flaskr.quotes.fetchers.stooq import Stooq
from pydantic import BaseModel, HttpUrl, ValidationError, Field
from dataclasses import dataclass
from typing import Optional


class PostData(BaseModel):
    name: str
    unit: str
    ticker: Optional[str]
    url: HttpUrl
    updateFrequency: QuoteUpdateFrequency
    currencyPairCheck: bool = Field(False, exclude=True)


@dataclass
class _ListEntry:
    """View-only wrapper pairing a Quote with its derived `active` flag
    (true when at least one non-trashed asset references this pricing source).
    Mirrors the `WalletData` pattern in `flaskr/apps/wallet/wallet.py`.
    """
    quote: Quote
    active: bool


def postNewItem():
    try:
        model = PostData(**request.form)
    except ValidationError:
        return ({'error': True, 'code': 1, 'message': "Invalid request"}, 400)

    data = model.dict(exclude_none=True)

    # The submit form still collects a single URL; store it as the first (and
    # only) entry of the `urls` array, which is now the source of truth.
    data['urls'] = [str(model.url)]
    data.pop('url', None)

    if Stooq.validUrl(model.url):
        data['stooqSymbol'] = Stooq.symbol(model.url)

    if model.currencyPairCheck:
        if 'currencyPairFrom' not in request.form.keys() or not model.unit:
            return ({'error': True, 'code': 2, 'message': "Invalid request"}, 400)

        # Yes, this is reversed in the application logic
        # The way it was designed is that you need to pay a quote ammount of 'from' currency to convert it to 1 'to'.
        # So having currency pair 'from': 'PLN', 'to': 'EUR', we take a quote (4.5) of 'PLN' to buy 1 'EUR'
        data['currencyPair'] = {
            'to': request.form['currencyPairFrom'],
            'from': model.unit,
        }

    # The pricing source must have at least one quote at creation time —
    # downstream consumers (HistoryPricing, wallet charts) assume a non-empty
    # quoteHistory and produce broken NaN timelines if one is missing.
    # If the initial fetch fails for any reason, surface the error to the
    # user via the standard error-toast contract and do NOT insert the doc.
    fetcher = QuotesFetcher.getInstance(model.url)
    if fetcher is None:
        return ({'error': True, 'code': 3,
                 'message': "No quote fetcher recognises this URL"}, 400)
    try:
        quote = fetcher.fetch()
    except FetchError as e:
        return ({'error': True, 'code': 3,
                 'message': f"Could not fetch initial quote: {e.msg}"}, 400)

    data['quoteHistory'] = [dict(
       timestamp=quote.timestamp,
       quote=float(quote.quote)
    )]

    addedId = db.get_db().quotes.insert_one(data).inserted_id
    return {'ok': True, 'id': str(addedId)}


def _getPipeline(includeTrashed = False):
    pipeline = []

    if not includeTrashed:
        pipeline.append({'$match': {'trashed': {'$ne': True}}})

    # Project the same shape as a full Quote document but trim quoteHistory
    # to the last entry — the listing only needs `lastQuote` (a Quote
    # property derived from quoteHistory) and pulling the full history would
    # be wasteful.
    pipeline.append({'$project': {
            '_id': 1,
            'name': 1,
            'urls': 1,
            'url': 1,
            'unit': 1,
            'ticker': 1,
            'stooqSymbol': 1,
            'updateFrequency': 1,
            'trashed': 1,
            'currencyPair': 1,
            'quoteHistory': {'$slice': ['$quoteHistory', -1]},
        }})

    return pipeline

def listAll():
    if request.method == 'GET':
        includeTrashed = 'all' in request.args
        activeQuoteIds = listActiveQuoteIds(used=True)
        sources = [
            _ListEntry(quote=Quote(**doc), active=doc['_id'] in activeQuoteIds)
            for doc in db.get_db().quotes.aggregate(_getPipeline(includeTrashed))
        ]

        return render_template("pricing/list.html", sources=sources, header=header.data())

    elif request.method == 'POST':
        return postNewItem()
