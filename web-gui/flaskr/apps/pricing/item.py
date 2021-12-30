from flask import render_template, request
from flaskr import db, header
from bson.objectid import ObjectId


def _getPipelineForQuotes(quoteId):
    pipeline = []
    pipeline.append({'$match' : { '_id' : ObjectId(quoteId) }})
    pipeline.append({'$project' : {
        '_id': 1,
        'name': 1,
        'url': 1,
        'unit': 1,
        'quoteHistory': 1,
        'updateFrequency': 1,
        'currencyPair': 1
    }})
    return pipeline


def item():
    if request.method == 'GET':
        quoteId = request.args.get('quoteId')
        if not quoteId:
            return ('', 400)

        quotes = list(db.get_db().quotes.aggregate(_getPipelineForQuotes(quoteId)))
        if not quotes:
            return ('', 404)

        return render_template("pricing/item.html", item=quotes[0], header=header.data())
