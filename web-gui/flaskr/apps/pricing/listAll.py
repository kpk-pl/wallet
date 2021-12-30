from flask import request, render_template, jsonify
from flaskr import db, header, stooq


def postNewItem():
    data = {}
    allowedKeys = ['name', 'ticker', 'url', 'unit', 'updateFrequency']

    for key in allowedKeys:
        if key in request.form.keys() and request.form[key]:
            data[key] = request.form[key]

    if 'updateFrequency' in data:
        allowedFreqs = ['daily', 'weekly', 'monthly']
        if data['updateFrequency'] not in allowedFreqs:
            return {'error': "Invalid update frequency provided"}

    if 'url' in data and stooq.Stooq.isValidUrl(data['url']):
        data['stooqSymbol'] = stooq.Stooq(url=data['url']).ticker

    addedId = db.get_db().quotes.insert(data)
    return {'ok': True, 'id': str(addedId)}


def _getPipeline():
    return [
        {'$project': {
            '_id': 1,
            'name': 1,
            'url': 1,
            'unit': 1,
            'lastQuote': {'$last': '$quoteHistory'}
        }}
    ]

def listAll():
    if request.method == 'GET':
        sources = list(db.get_db().quotes.aggregate(_getPipeline()))
        return render_template("pricing/list.html", sources=sources, header=header.data())
    elif request.method == 'POST':
        return postNewItem()
