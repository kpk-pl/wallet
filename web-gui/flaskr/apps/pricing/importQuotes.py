from flask import render_template, request
from flaskr import db, header
from bson.objectid import ObjectId


def _getPipeline(quoteId):
    pipeline = []
    pipeline.append({ "$match" : { "_id" : ObjectId(quoteId) } })
    pipeline.append({ "$project": {
        '_id': 1,
        'name': 1,
        'stooqSymbol': 1,
        'url': 1,
        'unit': 1,
        'quoteHistory': 1
    }})
    return pipeline


def importQuotes():
    if request.method == 'GET':
        quoteId = request.args.get('id')
        if not quoteId:
            return ('', 400)

        quoteItems = list(db.get_db().quotes.aggregate(_getPipeline(quoteId)))
        if not quoteItems:
            return ('', 404)

        return render_template("import_quotes.html", quote=quoteItems[0], header=header.data())
    elif request.method == 'POST':
        return ('', 204)
