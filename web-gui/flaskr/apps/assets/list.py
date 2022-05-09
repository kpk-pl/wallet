from flask import render_template, request, jsonify, current_app
from flaskr.session import Session
from bson.objectid import ObjectId
from flaskr import db, header
from flaskr.model import PyObjectId
from pydantic import BaseModel, HttpUrl, Field, ValidationError
from typing import Optional


def _getPipeline(label = None, includeTrashed = False):
    pipeline = []

    match = {}

    if not includeTrashed:
        match = { 'trashed': { '$ne' : True } }

    if label is not None:
        match['labels'] = label

    if match:
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
        'trashed': 1,
        'finalQuantity': { "$last": "$operations.finalQuantity" }
    }})

    return pipeline


def listAll():
    session = Session(['label', 'debug'])
    includeTrashed = 'all' in request.args
    assets = list(db.get_db().assets.aggregate(_getPipeline(session.label(), includeTrashed)))

    return render_template("assets/list.html", assets=assets, header=header.data(showLabels = True))


class PostBody(BaseModel):
    name: str
    ticker: Optional[str]
    currency: Optional[str] = Field(exclude=True)
    type: str
    institution: str
    category: str
    subcategory: Optional[str]
    region: Optional[str]
    link: Optional[HttpUrl]
    priceQuoteId: Optional[PyObjectId] = Field(exclude=True)
    labels: Optional[str] = Field(exclude=True)


def post():
    try:
        form = PostBody(**request.form)
    except ValidationError:
        return ({"error": True, "message": "Invalid request", "code": 10})

    data = form.dict(exclude_none=True)
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
    if currency != current_app.config['MAIN_CURRENCY']:
        currencyId = db.get_db().quotes.find_one(
            {"currencyPair.from": current_app.config['MAIN_CURRENCY'], "currencyPair.to": currency},
            {"_id": 1})

        if not currencyId and currency == 'GBX':
            currencyId = db.get_db().quotes.find_one(
                {"currencyPair.from": current_app.config['MAIN_CURRENCY'], "currencyPair.to": 'GBP'},
                {"_id": 1})

        if not currencyId:
            return ({"error": True, "message": f"Cannot find matching pricing source for given currency {currency}", "code": 3}, 400)

        data['currency']['quoteId'] = currencyId['_id']

    addedId = db.get_db().assets.insert(data)
    return jsonify(id=str(addedId))
