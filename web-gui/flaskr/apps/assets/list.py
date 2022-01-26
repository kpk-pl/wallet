from flask import render_template, request, jsonify
from flaskr.session import Session
from bson.objectid import ObjectId
from flaskr import db, header, typing
from flaskr.model import PyObjectId
from pydantic import BaseModel, HttpUrl
from typing import Optional


def _getPipeline(label = None):
    pipeline = []

    match = { 'trashed': { '$ne' : True } }
    if label is not None:
        match['labels'] = label

    pipeline.append({'$match': match})
    pipeline.append({'$project': {
        '_id': 1,
        'name': 1,
        'ticker': 1,
        'institution': 1,
        'type': 1,
        'category': 1,
        'subcategory': 1,
        'region': 1,
        'quantity': 1,
        'link': 1,
        'labels': 1,
        'finalQuantity': { "$last": "$operations.finalQuantity" }
    }})

    return pipeline


def listAll():
    session = Session(['label', 'debug'])
    assets = list(db.get_db().assets.aggregate(_getPipeline(session.label())))

    return render_template("assets/list.html", assets=assets, header=header.data(showLabels = True))


class PostBody(BaseModel):
    name: str
    ticker: str = ''
    currency: Optional[str]
    type: str
    institution: str
    category: str
    subcategory: str = ''
    region: Optional[str]
    link: str = ''
    priceQuoteId: Optional[PyObjectId]
    labels: Optional[str]


def post():
    form = PostBody(**request.form)

    copiedKeys = {'name', 'ticker', 'type', 'category', 'subcategory', 'region', 'institution'}
    data = form.dict(include=copiedKeys, exclude_none=True, exclude_defaults=True)

    if form.link:
        data['link'] = str(form.link)

    if form.labels:
        data['labels'] = form.labels.split(',')

    if not form.currency and not form.priceQuoteId:
        return ({"error": True, "message": "No currency source found", "code": 1}, 400)

    if form.priceQuoteId:
        data['pricing'] = { 'quoteId' : form.priceQuoteId }
        currencyName = db.get_db().quotes.find_one({"_id": form.priceQuoteId}, {"unit": 1})
        if not currencyName:
            return ({"error": True, "message": "Cannot find price source", "code": 2}, 400)

        data['currency'] = { 'name': currencyName['unit'] }
    else:
        data['currency'] = { 'name': form.currency }

    currency = data['currency']['name']
    if currency != typing.Currency.main:
        currencyId = db.get_db().quotes.find_one(
            {"currencyPair.from": typing.Currency.main, "currencyPair.to": currency},
            {"_id": 1})

        if not currencyId:
            return ({"error": True, "message": "Cannot find matching price source for given currency", "code": 3}, 400)

        data['currency']['quoteId'] = currencyId['_id']

    addedId = db.get_db().assets.insert(data)
    return jsonify(id=str(addedId))
