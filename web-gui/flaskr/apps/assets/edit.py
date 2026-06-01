from __future__ import annotations
from flask import render_template, request, jsonify
from flaskr import db, header
from flaskr.model import Asset, AssetPricingQuotes
from flaskr.model.assetPricing import AssetPricingParametrized
from bson.objectid import ObjectId
from pydantic import BaseModel, Field, ValidationError
from flaskr.model.types import HttpUrlStr
from typing import Optional
from .add import _quotesListPipeline
from .list import _toBson


class EditBody(BaseModel):
    name: str
    ticker: Optional[str] = None
    type: str
    institution: str
    category: str
    subcategory: Optional[str] = None
    region: Optional[str] = None
    link: Optional[HttpUrlStr] = None
    labels: Optional[str] = Field(default=None, exclude=True)


class ParametrizedEditBody(BaseModel):
    name: str
    institution: str
    type: str
    category: str
    subcategory: Optional[str] = None
    region: Optional[str] = None
    link: Optional[HttpUrlStr] = None
    labels: Optional[str] = None
    pricing: AssetPricingParametrized


def edit():
    assetId = request.args.get('id')
    if not assetId:
        return ('', 400)

    doc = db.get_db().assets.find_one({'_id': ObjectId(assetId)})
    if not doc:
        return ('', 404)

    if request.method == 'GET':
        asset = Asset(**doc)

        # The currency / pricing source is fixed at creation time because the
        # recorded operations depend on it, so it is only shown read-only.
        # Parametrized pricing (e.g. retail bonds) has no quote source to name.
        pricingName = None
        if isinstance(asset.pricing, AssetPricingQuotes):
            quote = db.get_db().quotes.find_one({'_id': asset.pricing.quoteId}, {'name': 1})
            if quote:
                pricingName = quote['name']

        # Parametrized assets (retail bonds) carry no region, so the field that
        # is mandatory for listed assets must not block saving here.
        isParametrized = asset.pricing is not None and not isinstance(asset.pricing, AssetPricingQuotes)

        quotesList = list(db.get_db().quotes.aggregate(_quotesListPipeline()))

        return render_template("assets/edit.html",
                               header=header.data(),
                               asset=asset,
                               pricingName=pricingName,
                               isParametrized=isParametrized,
                               quotesList=quotesList)

    if request.is_json:
        return _editParametrized(assetId, doc)

    # Empty inputs arrive as '' from the form; treat them as absent so optional
    # fields (e.g. an Optional[HttpUrl] link) don't fail validation on a blank.
    formData = {key: (value if value != '' else None) for key, value in request.form.items()}
    try:
        form = EditBody(**formData)
    except ValidationError:
        return ({"error": True, "message": "Invalid request", "code": 10}, 400)

    labels = [l.strip() for l in form.labels.split(',') if l.strip()] if form.labels else []

    update = {
        'name': form.name,
        'type': form.type,
        'institution': form.institution,
        'category': form.category,
    }
    unset = {}

    optional = [
        ('ticker', form.ticker),
        ('subcategory', form.subcategory),
        ('region', form.region),
        ('link', str(form.link) if form.link else None),
    ]
    for fieldName, value in optional:
        if value:
            update[fieldName] = value
        else:
            unset[fieldName] = ''

    if labels:
        update['labels'] = labels
    else:
        unset['labels'] = ''

    # Validate the whole asset (operations + pricing consistency) before saving
    # so an edit can never leave the document in an invalid state.
    candidate = dict(doc)
    candidate.update(update)
    for key in unset:
        candidate.pop(key, None)
    try:
        Asset(**candidate)
    except ValidationError as e:
        return ({"error": True, "message": str(e), "code": 11}, 400)

    operation = {'$set': update}
    if unset:
        operation['$unset'] = unset

    db.get_db().assets.update_one({'_id': ObjectId(assetId)}, operation)
    return jsonify(id=assetId)


def _editParametrized(assetId, doc):
    """Update a parametrized asset's editable fields and its pricing parameters.

    The currency is intentionally not editable here (recorded operations depend
    on it), so it is left untouched on the stored document.
    """
    try:
        form = ParametrizedEditBody(**request.get_json())
    except ValidationError as e:
        return ({"error": True, "message": str(e), "code": 10}, 400)

    for idx, item in enumerate(form.pricing.interest):
        if item.fixed is None and item.derived is None:
            return ({"error": True, "message": f"Interest period {idx + 1} needs a fixed and/or a derived rate", "code": 12}, 400)

    pricing = _toBson(form.pricing.model_dump(exclude_none=True))
    # Existing documents omit the default unit multiplier; keep edits consistent.
    if pricing.get('length', {}).get('multiplier') == 1:
        pricing['length'].pop('multiplier', None)

    update = {
        'name': form.name,
        'type': form.type,
        'institution': form.institution,
        'category': form.category,
        'pricing': pricing,
    }
    unset = {}

    optional = [
        ('subcategory', form.subcategory),
        ('region', form.region),
        ('link', str(form.link) if form.link else None),
    ]
    for fieldName, value in optional:
        if value:
            update[fieldName] = value
        else:
            unset[fieldName] = ''

    labels = [l.strip() for l in form.labels.split(',') if l.strip()] if form.labels else []
    if labels:
        update['labels'] = labels
    else:
        unset['labels'] = ''

    # Validate the whole asset (operations + pricing consistency) before saving.
    candidate = dict(doc)
    candidate.update(update)
    for key in unset:
        candidate.pop(key, None)
    try:
        Asset(**candidate)
    except ValidationError as e:
        return ({"error": True, "message": str(e), "code": 11}, 400)

    operation = {'$set': update}
    if unset:
        operation['$unset'] = unset

    db.get_db().assets.update_one({'_id': ObjectId(assetId)}, operation)
    return jsonify(id=assetId)
