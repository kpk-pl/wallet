from __future__ import annotations
from flask import render_template, request
from flaskr import db, header
from flaskr.model import Quote
from flaskr.model.quote import QuoteUpdateFrequency
from flaskr.quotes import Fetcher as QuotesFetcher, FetchError
from bson.objectid import ObjectId
from pydantic import BaseModel, HttpUrl, ValidationError
from typing import List, Optional


class EditData(BaseModel):
    name: str
    unit: str
    ticker: Optional[str]
    updateFrequency: QuoteUpdateFrequency
    urls: List[HttpUrl]


def edit():
    quoteId = request.args.get('quoteId')
    if not quoteId:
        return ('', 400)

    if request.method == 'GET':
        doc = db.get_db().quotes.find_one({'_id': ObjectId(quoteId)})
        if not doc:
            return ('', 404)

        model = Quote(**doc)
        data = dict(
            updateFrequencies=[f.name for f in QuoteUpdateFrequency],
        )
        return render_template("pricing/edit.html", header=header.data(), item=model, data=data)

    # POST — persist the edited fields. Only name, ticker, unit, update
    # frequency and the ordered list of links are editable here; currencyPair /
    # pricing parameters are left untouched.
    urls = [u.strip() for u in request.form.getlist('urls') if u and u.strip()]
    if not urls:
        return ({'error': True, 'code': 2, 'message': "At least one link is required"}, 400)

    try:
        model = EditData(
            name=request.form.get('name'),
            unit=request.form.get('unit'),
            ticker=request.form.get('ticker'),
            updateFrequency=request.form.get('updateFrequency'),
            urls=urls,
        )
    except ValidationError:
        return ({'error': True, 'code': 1, 'message': "Invalid request"}, 400)

    # Mirror the create flow's validation: every source URL must be recognised
    # by a fetcher and must yield a quote. This keeps a saved pricing source
    # from pointing at links nothing can fetch from.
    for url in model.urls:
        fetcher = QuotesFetcher.getInstance(url)
        if fetcher is None:
            return ({'error': True, 'code': 3,
                     'message': f"No quote fetcher recognises this URL: {url}"}, 400)
        try:
            fetcher.fetch(unit=model.unit)
        except FetchError as e:
            return ({'error': True, 'code': 3,
                     'message': f"Could not fetch a quote from {url}: {e.msg}"}, 400)

    update = {
        'name': model.name,
        'unit': model.unit,
        'updateFrequency': model.updateFrequency.value,
        'urls': [str(u) for u in model.urls],
    }
    # `urls` is the single source of truth; drop the legacy scalar `url`.
    unset = {'url': ''}

    if model.ticker:
        update['ticker'] = model.ticker
    else:
        unset['ticker'] = ''

    db.get_db().quotes.update_one(
        {'_id': ObjectId(quoteId)},
        {'$set': update, '$unset': unset},
    )

    return {'ok': True, 'id': quoteId}
