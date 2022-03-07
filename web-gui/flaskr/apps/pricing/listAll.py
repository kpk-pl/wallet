from flask import request, render_template, jsonify
from flaskr import db, header, stooq
from pydantic import BaseModel, HttpUrl, ValidationError, Field
from typing import Optional
from enum import Enum


class PostDataUpdateFrequency(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class PostData(BaseModel):
    name: str
    ticker: Optional[str]
    url: HttpUrl
    unit: Optional[str]
    updateFrequency: PostDataUpdateFrequency
    currencyPairCheck: bool = Field(False, exclude=True)


def postNewItem():
    try:
        model = PostData(**request.form)
    except ValidationError as e:
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
        data['currencyPair'] = {
            'to': request.form['currencyPairFrom'],
            'from': model.unit
        }


    addedId = db.get_db().quotes.insert(data)
    return {'ok': True, 'id': str(addedId)}


def _getPipeline():
    return [
        {'$project': {
            '_id': 1,
            'name': 1,
            'url': 1,
            'unit': 1,
            'currencyPair': 1,
            'lastQuote': {'$last': '$quoteHistory'}
        }}
    ]

def listAll():
    if request.method == 'GET':
        sources = list(db.get_db().quotes.aggregate(_getPipeline()))
        return render_template("pricing/list.html", sources=sources, header=header.data())
    elif request.method == 'POST':
        return postNewItem()
