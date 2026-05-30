from __future__ import annotations
from flask import render_template, request, jsonify, current_app
from flaskr.session import Session
from bson.objectid import ObjectId
from bson.decimal128 import Decimal128
from decimal import Decimal
from flaskr import db, header, model
from flaskr.model import PyObjectId
from flaskr.model.assetPricing import AssetPricingParametrized
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


class ParametrizedPostBody(BaseModel):
    name: str
    institution: str
    type: str
    category: str
    subcategory: Optional[str]
    region: Optional[str]
    link: Optional[HttpUrl]
    currency: str
    labels: Optional[str]
    pricing: AssetPricingParametrized


def _resolveCurrency(currencyName):
    """Build the stored currency sub-document for an asset.

    Returns (currency, error). For foreign currencies a matching PLN->currency
    quote must exist; when it cannot be found `error` is a Flask response tuple.
    """
    currency = {'name': currencyName}
    if currencyName == current_app.config['MAIN_CURRENCY']:
        return currency, None

    currencyId = db.get_db().quotes.find_one(
        {"currencyPair.from": current_app.config['MAIN_CURRENCY'], "currencyPair.to": currencyName},
        {"_id": 1})

    if not currencyId and currencyName == 'GBX':
        currencyId = db.get_db().quotes.find_one(
            {"currencyPair.from": current_app.config['MAIN_CURRENCY'], "currencyPair.to": 'GBP'},
            {"_id": 1})

    if not currencyId:
        return None, ({"error": True, "message": f"Cannot find matching pricing source for given currency {currencyName}", "code": 3}, 400)

    currency['quoteId'] = currencyId['_id']
    return currency, None


def _toBson(value):
    """Recursively convert Decimal values to Decimal128 so pymongo can store them."""
    if isinstance(value, dict):
        return {key: _toBson(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_toBson(item) for item in value]
    if isinstance(value, Decimal):
        return Decimal128(value)
    return value


def post():
    if request.is_json:
        return _postParametrized()

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
        priceSource = db.get_db().quotes.find_one({"_id": form.priceQuoteId}, {"unit": 1})
        if not priceSource:
            return ({"error": True, "message": "Cannot find price source", "code": 2}, 400)

        currencyName = priceSource['unit']
    else:
        currencyName = form.currency

    currency, err = _resolveCurrency(currencyName)
    if err:
        return err
    data['currency'] = currency

    addedId = db.get_db().assets.insert_one(data).inserted_id
    return jsonify(id=str(addedId))


def _postParametrized():
    try:
        form = ParametrizedPostBody(**request.get_json())
    except ValidationError as e:
        return ({"error": True, "message": str(e), "code": 10}, 400)

    for idx, item in enumerate(form.pricing.interest):
        if item.fixed is None and item.derived is None:
            return ({"error": True, "message": f"Interest period {idx + 1} needs a fixed and/or a derived rate", "code": 12}, 400)

    currency, err = _resolveCurrency(form.currency)
    if err:
        return err

    pricing = _toBson(form.pricing.dict(exclude_none=True))
    # Existing documents omit the default unit multiplier; keep new ones consistent.
    if pricing.get('length', {}).get('multiplier') == 1:
        pricing['length'].pop('multiplier', None)

    data = {
        'name': form.name,
        'institution': form.institution,
        'type': form.type,
        'category': form.category,
        'currency': currency,
        'pricing': pricing,
    }
    if form.subcategory:
        data['subcategory'] = form.subcategory
    if form.region:
        data['region'] = form.region
    if form.link:
        data['link'] = str(form.link)
    if form.labels:
        labels = [label.strip() for label in form.labels.split(',') if label.strip()]
        if labels:
            data['labels'] = labels

    # Validate the whole asset (pricing + type consistency) before persisting.
    try:
        model.Asset(_id=ObjectId(), **data)
    except ValidationError as e:
        return ({"error": True, "message": str(e), "code": 11}, 400)

    addedId = db.get_db().assets.insert_one(data).inserted_id
    return jsonify(id=str(addedId))
