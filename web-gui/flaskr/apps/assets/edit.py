from __future__ import annotations
from flask import render_template, request, jsonify
from flaskr import db, header
from flaskr.model import Asset
from bson.objectid import ObjectId
from pydantic import BaseModel, HttpUrl, Field, ValidationError
from typing import Optional


class EditBody(BaseModel):
    name: str
    ticker: Optional[str]
    type: str
    institution: str
    category: str
    subcategory: Optional[str]
    region: Optional[str]
    link: Optional[HttpUrl]
    labels: Optional[str] = Field(exclude=True)


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
        pricingName = None
        if asset.pricing and asset.pricing.quoteId:
            quote = db.get_db().quotes.find_one({'_id': asset.pricing.quoteId}, {'name': 1})
            if quote:
                pricingName = quote['name']

        return render_template("assets/edit.html",
                               header=header.data(),
                               asset=asset,
                               pricingName=pricingName)

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
