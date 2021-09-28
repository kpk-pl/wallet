from flask import render_template, request, jsonify
from bson.objectid import ObjectId
from flaskr import db, header
from flaskr.stooq import Stooq


def listAll():
    if request.method == 'GET':
        pipeline = [
            { "$match" : { 'trashed': { '$ne' : True } } },
            { "$project" : {
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
                'finalQuantity': { "$last": "$operations.finalQuantity" }
            }}
        ]
        assets = list(db.get_db().assets.aggregate(pipeline))

        return render_template("list.html", assets=assets, header=header.data())

    elif request.method == 'POST':
        data = {}

        allowedKeys = ['name', 'ticker', 'link', 'type', 'category', 'subcategory', 'region', 'institution']
        for key in allowedKeys:
            if key in request.form.keys() and request.form[key]:
                data[key] = request.form[key]

        if data['link'].startswith("https://stooq.pl"):
            data['stooqSymbol'] = Stooq(url=data['link']).ticker

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
