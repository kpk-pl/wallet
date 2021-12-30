from flask import render_template, request, jsonify
from flaskr.session import Session
from bson.objectid import ObjectId
from flaskr import db, header


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
    if request.method == 'GET':
        session = Session(['label', 'debug'])
        assets = list(db.get_db().assets.aggregate(_getPipeline(session.label())))

        return render_template("assets/list.html", assets=assets, header=header.data(showLabels = True))

    elif request.method == 'POST':
        data = {}

        allowedKeys = ['name', 'ticker', 'link', 'type', 'category', 'subcategory', 'region', 'institution']
        for key in allowedKeys:
            if key in request.form.keys() and request.form[key]:
                data[key] = request.form[key]

        if 'labels' in request.form:
            data['labels'] = request.form['labels'].split(',')

        if 'priceQuoteId' in request.form:
            data['pricing'] = {
                'quoteId': ObjectId(request.form['priceQuoteId'])
            }

        currency = request.form['currency']
        data['currency'] = {
            'name': currency
        }
        if currency != 'PLN':
            currencyId = db.get_db().quotes.find_one({"name": currency + "PLN"}, {"_id": 1})
            if currencyId:
                data['currency']['quoteId'] = currencyId['_id']

        addedId = db.get_db().assets.insert(data)
        return jsonify(id=str(addedId))
